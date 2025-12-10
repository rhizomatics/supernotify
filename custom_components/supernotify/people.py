import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.person.const import DOMAIN as PERSON_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_STATE,
    CONF_ALIAS,
    CONF_DEVICE_ID,
    CONF_ENABLED,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.util import slugify

from . import (
    ATTR_ALIAS,
    ATTR_EMAIL,
    ATTR_ENABLED,
    ATTR_MOBILE_APP_ID,
    ATTR_PERSON_ID,
    ATTR_PHONE,
    ATTR_USER_ID,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TRACKER,
    CONF_EMAIL,
    CONF_MANUFACTURER,
    CONF_MOBILE_APP_ID,
    CONF_MOBILE_DEVICES,
    CONF_MOBILE_DISCOVERY,
    CONF_MODEL,
    CONF_PERSON,
    CONF_PHONE_NUMBER,
    CONF_TARGET,
    OCCUPANCY_ALL,
    OCCUPANCY_ALL_IN,
    OCCUPANCY_ALL_OUT,
    OCCUPANCY_ANY_IN,
    OCCUPANCY_ANY_OUT,
    OCCUPANCY_NONE,
    OCCUPANCY_ONLY_IN,
    OCCUPANCY_ONLY_OUT,
)
from .common import ensure_list
from .hass_api import HomeAssistantAPI
from .model import DeliveryCustomization, Target

if TYPE_CHECKING:
    from homeassistant.core import State
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry

_LOGGER = logging.getLogger(__name__)


class Recipient:
    """Recipient to distinguish from the native HA Person"""

    def __init__(self, config: dict[str, Any] | None, default_mobile_discovery: bool = True) -> None:
        config = config or {}
        self.entity_id = config[CONF_PERSON]
        self.name = f"recipient_{self.entity_id.replace('person.', '')}"
        self.alias: str | None = config.get(CONF_ALIAS)
        self.email: str | None = config.get(CONF_EMAIL)
        self.phone_number: str | None = config.get(CONF_PHONE_NUMBER)
        self.user_id: str | None = config.get(ATTR_USER_ID)
        self.state: str | None = config.get(ATTR_STATE)

        self._target: Target = Target(config.get(CONF_TARGET, {}), target_data=config.get(CONF_DATA))
        self.delivery: dict[str, DeliveryCustomization] = {
            k: DeliveryCustomization(v, target_specific=True) for k, v in config.get(CONF_DELIVERY, {}).items()
        }
        self.enabled: bool = config.get(CONF_ENABLED, True)
        self.mobile_discovery: bool = config.get(CONF_MOBILE_DISCOVERY, default_mobile_discovery)
        self.mobile_devices: list[dict[str, Any]] = config.get(CONF_MOBILE_DEVICES) or []

    def initialize(self, people_registry: "PeopleRegistry") -> None:

        self._target.extend(ATTR_PERSON_ID, [self.entity_id])
        if self.email:
            self._target.extend(ATTR_EMAIL, self.email)
        if self.phone_number:
            self._target.extend(ATTR_PHONE, self.phone_number)
        if self.mobile_discovery:
            discovered_devices: list[dict[str, Any]] = people_registry.mobile_devices_for_person(self.entity_id)
            self.mobile_devices.extend(discovered_devices)
            if discovered_devices:
                _LOGGER.info("SUPERNOTIFY Auto configured %s for mobile devices %s", self.entity_id, discovered_devices)
            else:
                _LOGGER.warning("SUPERNOTIFY Unable to find mobile devices for %s", self.entity_id)
        if self.mobile_devices:
            self._target.extend(ATTR_MOBILE_APP_ID, [d[CONF_MOBILE_APP_ID] for d in self.mobile_devices])
        if not self.user_id or not self.alias:
            attrs: dict[str, Any] | None = people_registry.person_attributes(self.entity_id)
            if attrs:
                if attrs.get(ATTR_USER_ID) and isinstance(attrs.get(ATTR_USER_ID), str):
                    self.user_id = attrs.get(ATTR_USER_ID)
                if attrs.get(ATTR_ALIAS) and isinstance(attrs.get(ATTR_ALIAS), str):
                    self.alias = attrs.get(ATTR_ALIAS)
                if not self.alias and attrs.get(ATTR_FRIENDLY_NAME) and isinstance(attrs.get(ATTR_FRIENDLY_NAME), str):
                    self.alias = attrs.get(ATTR_FRIENDLY_NAME)

    def target(self, delivery_name: str) -> Target:
        recipient_target = self._target
        personal_delivery = self.delivery.get(delivery_name)
        if personal_delivery and personal_delivery.enabled:
            if personal_delivery.target and personal_delivery.target.has_targets():
                recipient_target += personal_delivery.target
            if personal_delivery.data:
                recipient_target += Target([], target_data=personal_delivery.data, target_specific_data=True)
        return recipient_target

    def as_dict(self, occupancy_only: bool = False, **_kwargs: Any) -> dict[str, Any]:
        result = {CONF_PERSON: self.entity_id, CONF_ENABLED: self.enabled, ATTR_STATE: self.state}
        if not occupancy_only:
            result.update({
                CONF_ALIAS: self.alias,
                CONF_EMAIL: self.email,
                CONF_PHONE_NUMBER: self.phone_number,
                ATTR_USER_ID: self.user_id,
                CONF_MOBILE_DISCOVERY: self.mobile_discovery,
                CONF_MOBILE_DEVICES: self.mobile_devices,
                CONF_TARGET: self._target.as_dict() if self._target else None,
                CONF_DELIVERY: {d: c.as_dict() for d, c in self.delivery.items()} if self.delivery else None,
            })
        return result

    def attributes(self) -> dict[str, Any]:
        """For exposure as entity state"""
        attrs: dict[str, Any] = {
            ATTR_ENTITY_ID: self.entity_id,
            ATTR_ENABLED: self.enabled,
            CONF_EMAIL: self.email,
            CONF_PHONE_NUMBER: self.phone_number,
            ATTR_USER_ID: self.user_id,
            CONF_MOBILE_DEVICES: self.mobile_devices,
            CONF_MOBILE_DISCOVERY: self.mobile_discovery,
            CONF_TARGET: self._target.as_dict() if self._target else None,
            CONF_DELIVERY: {d: c.as_dict() for d, c in self.delivery.items()} if self.delivery else None,
        }
        if self.alias:
            attrs[ATTR_FRIENDLY_NAME] = self.alias
        return attrs


class PeopleRegistry:
    def __init__(
        self,
        recipients: list[dict[str, Any]],
        hass_api: HomeAssistantAPI,
        discover: bool = False,
        mobile_discovery: bool = True,
    ) -> None:
        self.hass_api = hass_api
        self.people: dict[str, Recipient] = {}
        self._recipients: list[dict[str, Any]] = ensure_list(recipients)
        self.entity_registry = entity_registry
        self.device_registry = device_registry
        self.mobile_discovery = mobile_discovery
        self.discover = discover

    def initialize(self) -> None:
        recipients: dict[str, dict[str, Any]] = {}
        if self.discover:
            entity_ids = self.find_people()
            if entity_ids:
                recipients = {entity_id: {CONF_PERSON: entity_id} for entity_id in entity_ids}
                _LOGGER.info("SUPERNOTIFY Auto-discovered people: %s", entity_ids)

        for r in self._recipients:
            if CONF_PERSON not in r or not r[CONF_PERSON]:
                _LOGGER.warning("SUPERNOTIFY Skipping invalid recipient with no 'person' key:%s", r)
                continue
            person_id = r[CONF_PERSON]
            if person_id in recipients:
                _LOGGER.debug("SUPERNOTIFY Overriding %s entity defaults from recipient config", person_id)
                recipients[person_id].update(r)
            else:
                recipients[person_id] = r

        for r in recipients.values():
            recipient: Recipient = Recipient(r, default_mobile_discovery=self.mobile_discovery)
            recipient.initialize(self)

            self.people[recipient.entity_id] = recipient

    def person_attributes(self, entity_id: str) -> dict[str, Any] | None:
        state: State | None = self.hass_api.get_state(entity_id)
        if state is not None and state.attributes:
            return state.attributes
        return None

    def find_people(self) -> list[str]:
        return self.hass_api.entity_ids_for_domain(PERSON_DOMAIN)

    def enabled_recipients(self) -> list[Recipient]:
        return [p for p in self.people.values() if p.enabled]

    def filter_recipients_by_occupancy(self, delivery_occupancy: str) -> list[Recipient]:
        if delivery_occupancy == OCCUPANCY_NONE:
            return []

        people = [p for p in self.people.values() if p.enabled]
        if delivery_occupancy == OCCUPANCY_ALL:
            return people

        occupancy = self.determine_occupancy()

        away = occupancy[STATE_NOT_HOME]
        at_home = occupancy[STATE_HOME]
        if delivery_occupancy == OCCUPANCY_ALL_IN:
            return people if len(away) == 0 else []
        if delivery_occupancy == OCCUPANCY_ALL_OUT:
            return people if len(at_home) == 0 else []
        if delivery_occupancy == OCCUPANCY_ANY_IN:
            return people if len(at_home) > 0 else []
        if delivery_occupancy == OCCUPANCY_ANY_OUT:
            return people if len(away) > 0 else []
        if delivery_occupancy == OCCUPANCY_ONLY_IN:
            return at_home
        if delivery_occupancy == OCCUPANCY_ONLY_OUT:
            return away

        _LOGGER.warning("SUPERNOTIFY Unknown occupancy tested: %s", delivery_occupancy)
        return []

    def refresh_tracker_state(self) -> None:
        for person_id, person_config in self.people.items():
            # TODO: possibly rate limit this
            if person_config.enabled:
                try:
                    tracker: State | None = self.hass_api.get_state(person_id)
                    if tracker is None:
                        person_config.state = None
                    elif isinstance(tracker.state, str):
                        person_config.state = tracker.state
                    else:
                        _LOGGER.warning("SUPERNOTIFY Unexpected state %s for %s", tracker.state, person_id)
                except Exception as e:
                    _LOGGER.warning("SUPERNOTIFY Unable to determine occupied status for %s: %s", person_id, e)

    def determine_occupancy(self) -> dict[str, list[Recipient]]:
        results: dict[str, list[Recipient]] = {STATE_HOME: [], STATE_NOT_HOME: []}
        self.refresh_tracker_state()
        for person_config in self.people.values():
            if person_config.enabled:
                if person_config.state in (None, STATE_HOME):
                    # default to at home if unknown tracker
                    results[STATE_HOME].append(person_config)
                else:
                    results[STATE_NOT_HOME].append(person_config)
        return results

    def mobile_devices_for_person(self, person_entity_id: str, validate_targets: bool = False) -> list[dict[str, Any]]:
        """Auto detect mobile_app targets for a person.

        Targets not currently validated as async registration may not be complete at this stage

        Args:
        ----
            person_entity_id (str): _description_
            validate_targets (bool, optional): _description_. Defaults to False.

        Returns:
        -------
            list: mobile target actions for this person

        """
        mobile_devices = []
        device_trackers: list[str] | None = None
        try:
            person_state = self.hass_api.get_state(person_entity_id)
            if not person_state:
                _LOGGER.warning("SUPERNOTIFY Unable to resolve %s", person_entity_id)
            else:
                device_trackers = person_state.attributes.get("device_trackers", [])
                _LOGGER.debug("SUPERNOTIFY Found device trackers for %s:%s", person_entity_id, ",".join(device_trackers))
        except Exception as e:
            device_trackers = None
            _LOGGER.warning("SUPERNOTIFY Device_trackers data can't be retrieved for %s: %s", person_entity_id, e)
        if device_trackers:
            ent_reg: EntityRegistry | None = self.hass_api.entity_registry()
            dev_reg: DeviceRegistry | None = self.hass_api.device_registry()
            if not ent_reg or not dev_reg:
                _LOGGER.warning("SUPERNOTIFY Unable to access entity or device registries for %s", person_entity_id)
            else:
                for d_t in device_trackers:
                    entity = ent_reg.async_get(d_t)
                    if entity and entity.platform == "mobile_app" and entity.device_id:
                        device = dev_reg.async_get(entity.device_id)
                        if not device:
                            _LOGGER.warning("SUPERNOTIFY Unable to find device %s", entity.device_id)
                        else:
                            mobile_app_id = f"mobile_app_{slugify(device.name)}"
                            if validate_targets and not self.hass_api.has_service("notify", mobile_app_id):
                                _LOGGER.warning("SUPERNOTIFY Unable to find notify action <%s>", mobile_app_id)
                            else:
                                mobile_devices.append({
                                    CONF_MANUFACTURER: device.manufacturer,
                                    CONF_MODEL: device.model,
                                    CONF_MOBILE_APP_ID: mobile_app_id,
                                    CONF_DEVICE_TRACKER: d_t,
                                    CONF_DEVICE_ID: device.id,
                                    CONF_DEVICE_NAME: device.name,
                                    # CONF_DEVICE_LABELS: device.labels,
                                })
                    else:
                        _LOGGER.debug("SUPERNOTIFY Ignoring device tracker %s", d_t)

        return mobile_devices
