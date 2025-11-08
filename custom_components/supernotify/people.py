import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_STATE, CONF_DEVICE_ID, STATE_HOME, STATE_NOT_HOME
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.util import slugify

from . import (
    ATTR_USER_ID,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TRACKER,
    CONF_MANUFACTURER,
    CONF_MOBILE_DEVICES,
    CONF_MOBILE_DISCOVERY,
    CONF_MODEL,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
)
from .common import ensure_list
from .context import HomeAssistantAccess

if TYPE_CHECKING:
    from homeassistant.core import State
    from homeassistant.helpers.device_registry import DeviceRegistry
    from homeassistant.helpers.entity_registry import EntityRegistry

_LOGGER = logging.getLogger(__name__)


class PeopleRegistry:
    def __init__(self, recipients: list[dict[str, Any]], hass_access: HomeAssistantAccess) -> None:
        self.hass_access = hass_access
        self.people: dict[str, dict[str, Any]] = {}
        self._recipients: list[dict[str, Any]] = ensure_list(recipients)
        self.entity_registry = entity_registry
        self.device_registry = device_registry

    def initialize(self) -> None:
        for r in self._recipients:
            if r.get(CONF_MOBILE_DISCOVERY):
                r[CONF_MOBILE_DEVICES].extend(self.mobile_devices_for_person(r[CONF_PERSON]))
                if r.get(CONF_MOBILE_DEVICES):
                    _LOGGER.info("SUPERNOTIFY Auto configured %s for mobile devices %s", r[CONF_PERSON], r[CONF_MOBILE_DEVICES])
                else:
                    _LOGGER.warning("SUPERNOTIFY Unable to find mobile devices for %s", r[CONF_PERSON])

            state: State | None = self.hass_access.get_state(r[CONF_PERSON])
            if state is not None:
                r[ATTR_USER_ID] = state.attributes.get(ATTR_USER_ID)
            self.people[r[CONF_PERSON]] = r

    def refresh_tracker_state(self) -> None:
        for person, person_config in self.people.items():
            # TODO: possibly rate limit this
            try:
                tracker: State | None = self.hass_access.get_state(person)
                if tracker is None:
                    person_config[ATTR_STATE] = None
                else:
                    person_config[ATTR_STATE] = tracker.state
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to determine occupied status for %s: %s", person, e)

    def determine_occupancy(self) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {STATE_HOME: [], STATE_NOT_HOME: []}
        self.refresh_tracker_state()
        for person_config in self.people.values():
            if person_config.get(ATTR_STATE) in (None, STATE_HOME):
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
        person_state = self.hass_access.get_state(person_entity_id)
        if not person_state:
            _LOGGER.warning("SUPERNOTIFY Unable to resolve %s", person_entity_id)
        else:
            ent_reg: EntityRegistry | None = self.hass_access.entity_registry()
            dev_reg: DeviceRegistry | None = self.hass_access.device_registry()
            if not ent_reg or not dev_reg:
                _LOGGER.warning("SUPERNOTIFY Unable to access entity or device registries for %s", person_entity_id)
            else:
                for d_t in person_state.attributes.get("device_trackers", ()):
                    entity = ent_reg.async_get(d_t)
                    if entity and entity.platform == "mobile_app" and entity.device_id:
                        device = dev_reg.async_get(entity.device_id)
                        if not device:
                            _LOGGER.warning("SUPERNOTIFY Unable to find device %s", entity.device_id)
                        else:
                            notify_action = f"mobile_app_{slugify(device.name)}"
                            if validate_targets and not self.hass_access.has_service("notify", notify_action):
                                _LOGGER.warning("SUPERNOTIFY Unable to find notify action <%s>", notify_action)
                            else:
                                mobile_devices.append({
                                    CONF_MANUFACTURER: device.manufacturer,
                                    CONF_MODEL: device.model,
                                    CONF_NOTIFY_ACTION: notify_action,
                                    CONF_DEVICE_TRACKER: d_t,
                                    CONF_DEVICE_ID: device.id,
                                    CONF_DEVICE_NAME: device.name,
                                    # CONF_DEVICE_LABELS: device.labels,
                                })
                    else:
                        _LOGGER.debug("SUPERNOTIFY Ignoring device tracker %s", d_t)

        return mobile_devices
