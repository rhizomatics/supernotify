from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_STATE,
    CONF_DEFAULT,
    CONF_DEVICE_ID,
    CONF_ENABLED,
    CONF_METHOD,
    CONF_NAME,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.config_validation import boolean
from homeassistant.helpers.network import get_url
from homeassistant.util import slugify

from custom_components.supernotify.archive import ArchiveTopic, NotificationArchive
from custom_components.supernotify.common import ensure_list, safe_get
from custom_components.supernotify.snoozer import Snoozer

from . import (
    ATTR_USER_ID,
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_CAMERA,
    CONF_DATA,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TRACKER,
    CONF_MANUFACTURER,
    CONF_MOBILE_DEVICES,
    CONF_MOBILE_DISCOVERY,
    CONF_MODEL,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
    CONF_SELECTION,
    CONF_TARGETS_REQUIRED,
    DELIVERY_SELECTION_IMPLICIT,
    DOMAIN,
    SCENARIO_DEFAULT,
    SCENARIO_TEMPLATE_ATTRS,
    SELECTION_DEFAULT,
    SELECTION_FALLBACK,
    SELECTION_FALLBACK_ON_ERROR,
)
from .scenario import Scenario

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, State
    from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry

    from custom_components.supernotify.delivery_method import DeliveryMethod

_LOGGER = logging.getLogger(__name__)


class Context:
    def __init__(
        self,
        hass: HomeAssistant | None = None,
        deliveries: dict[str, Any] | None = None,
        links: list[str] | None = None,
        recipients: list[dict[str, Any]] | None = None,
        mobile_actions: dict[str, Any] | None = None,
        template_path: str | None = None,
        media_path: str | None = None,
        archive_config: dict[str, str] | None = None,
        scenarios: dict[str, dict[str, Any]] | None = None,
        method_configs: dict[str, Any] | None = None,
        cameras: list[dict[str, Any]] | None = None,
        method_types: list[type[DeliveryMethod]] | None = None,
    ) -> None:
        self.hass: HomeAssistant | None = None
        self.hass_internal_url: str
        self.hass_external_url: str
        if hass:
            self.hass = hass
            self.hass_name = hass.config.location_name
            try:
                self.hass_internal_url = get_url(hass, prefer_external=False)
            except Exception as e:
                self.hass_internal_url = f"http://{socket.gethostname()}"
                _LOGGER.warning("SUPERNOTIFY could not get internal hass url, defaulting to %s: %s", self.hass_internal_url, e)
            try:
                self.hass_external_url = get_url(hass, prefer_external=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY could not get external hass url, defaulting to internal url: %s", e)
                self.hass_external_url = self.hass_internal_url
        else:
            self.hass_internal_url = ""
            self.hass_external_url = ""
            self.hass_name = "!UNDEFINED!"
            _LOGGER.warning("SUPERNOTIFY Configured without HomeAssistant instance")

        _LOGGER.debug(
            "SUPERNOTIFY Configured for HomeAssistant instance %s at %s , %s",
            self.hass_name,
            self.hass_internal_url,
            self.hass_external_url,
        )

        if not self.hass_internal_url or not self.hass_internal_url.startswith("http"):
            _LOGGER.warning("SUPERNOTIFY invalid internal hass url %s", self.hass_internal_url)

        self.links: list[dict[str, Any]] = ensure_list(links)
        # raw configured deliveries
        self._deliveries: dict[str, Any] = deliveries if isinstance(deliveries, dict) else {}
        # validated deliveries
        self.deliveries: dict[str, Any] = {}
        self._recipients: list[dict[str, Any]] = ensure_list(recipients)
        self.mobile_actions: dict[str, Any] = mobile_actions or {}
        self.template_path: Path | None = Path(template_path) if template_path else None
        self.media_path: Path | None = Path(media_path) if media_path else None
        archive_config = archive_config or {}
        self.archive: NotificationArchive = NotificationArchive(
            bool(archive_config.get(CONF_ENABLED, False)),
            archive_config.get(CONF_ARCHIVE_PATH),
            archive_config.get(CONF_ARCHIVE_DAYS),
        )
        archive_topic = archive_config.get(CONF_ARCHIVE_MQTT_TOPIC)
        self.archive_topic: ArchiveTopic | None = None
        if archive_topic is not None and self.hass:
            self.archive_topic = ArchiveTopic(
                self.hass,
                archive_topic,
                int(archive_config.get(CONF_ARCHIVE_MQTT_QOS, 0)),
                boolean(archive_config.get(CONF_ARCHIVE_MQTT_RETAIN, True)),
            )
        else:
            self.archive_topic = None
        self.cameras: dict[str, Any] = {c[CONF_CAMERA]: c for c in cameras} if cameras else {}
        self.methods: dict[str, DeliveryMethod] = {}
        self._method_configs: dict[str, Any] = method_configs or {}
        self.scenarios: dict[str, Scenario] = {}
        self.people: dict[str, dict[str, Any]] = {}
        self._config_scenarios: dict[str, Any] = scenarios or {}
        self.content_scenario_templates: dict[str, Any] = {}
        self.delivery_by_scenario: dict[str, list[str]] = {SCENARIO_DEFAULT: []}
        self.fallback_on_error: dict[str, dict[str, Any]] = {}
        self.fallback_by_default: dict[str, dict[str, Any]] = {}
        self._entity_registry: entity_registry.EntityRegistry | None = None
        self._device_registry: device_registry.DeviceRegistry | None = None
        self._method_types: list[type[DeliveryMethod]] = method_types or []
        self.snoozer = Snoozer()
        # test harness support
        self._create_default_scenario: bool = False
        self._method_instances: list[DeliveryMethod] | None = None

    async def initialize(self) -> None:
        await self._register_delivery_methods(
            delivery_methods=self._method_instances, delivery_method_classes=self._method_types
        )

        self.people = self.setup_people(self._recipients)

        if self._config_scenarios and self.hass:
            for scenario_name, scenario_definition in self._config_scenarios.items():
                scenario = Scenario(scenario_name, scenario_definition, self.hass)
                if await scenario.validate(
                    valid_deliveries=list(self.deliveries), valid_action_groups=list(self.mobile_actions)
                ):
                    self.scenarios[scenario_name] = scenario

        if self.template_path and not self.template_path.exists():
            _LOGGER.warning("SUPERNOTIFY template path not found at %s", self.template_path)
            self.template_path = None

        if self.media_path and not self.media_path.exists():
            _LOGGER.info("SUPERNOTIFY media path not found at %s", self.media_path)
            try:
                self.media_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY media path %s cannot be created: %s", self.media_path, e)
                self.raise_issue("media_path", "media_path", {"path": str(self.media_path), "error": str(e)})
                self.media_path = None
        if self.media_path is not None:
            _LOGGER.info("SUPERNOTIFY abs media path: %s", self.media_path.absolute())
        if self.archive:
            self.archive.initialize()
        default_deliveries: dict[str, Any] = self.initialize_deliveries()
        self.initialize_scenarios(default_deliveries, default_scenario=self._create_default_scenario)

    def configure_for_tests(
        self, method_instances: list[DeliveryMethod] | None = None, create_default_scenario: bool = False
    ) -> None:
        self._create_default_scenario = create_default_scenario
        self._method_instances = method_instances

    def raise_issue(
        self,
        issue_id: str,
        issue_key: str,
        issue_map: dict[str, str],
        severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
        learn_more_url: str = "https://jeyrb.github.io/hass_supernotify",
    ) -> None:
        if not self.hass:
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            translation_key=issue_key,
            translation_placeholders=issue_map,
            severity=severity,
            learn_more_url=learn_more_url,
        )

    def initialize_deliveries(self) -> dict[str, Any]:
        default_deliveries = {}
        if self._deliveries:
            for d, dc in self._deliveries.items():
                method = self.methods.get(dc[CONF_METHOD])
                if method:
                    for k, v in method.default.items():
                        dc.setdefault(k, v)
                else:
                    _LOGGER.warning(f"SUPERNOTIFY Unknown method {dc[CONF_METHOD]} for delivery {d}")
                    self.raise_issue(
                        f"delivery_{d}_unknown_method{dc[CONF_METHOD]}",
                        issue_key="delivery_unknown_method",
                        issue_map={"delivery": d, "method": dc[CONF_METHOD]},
                    )
                    dc[CONF_ENABLED] = False
                if dc.get(CONF_ENABLED, True):
                    if SELECTION_FALLBACK_ON_ERROR in dc.get(CONF_SELECTION, [SELECTION_DEFAULT]):
                        self.fallback_on_error[d] = dc
                    if SELECTION_FALLBACK in dc.get(CONF_SELECTION, [SELECTION_DEFAULT]):
                        self.fallback_by_default[d] = dc
                    if SELECTION_DEFAULT in dc.get(CONF_SELECTION, [SELECTION_DEFAULT]):
                        default_deliveries[d] = dc

                if not dc.get(CONF_NAME):
                    dc[CONF_NAME] = d  # for minimal tests

        return default_deliveries

    def initialize_scenarios(self, default_deliveries: dict[str, Any], default_scenario: bool = False) -> None:
        for scenario_name, scenario in self.scenarios.items():
            self.delivery_by_scenario.setdefault(scenario_name, [])
            if scenario.delivery_selection == DELIVERY_SELECTION_IMPLICIT:
                scenario_deliveries: list[str] = list(default_deliveries.keys())
            else:
                scenario_deliveries = []
            scenario_definition_delivery = scenario.delivery
            scenario_deliveries.extend(s for s in scenario_definition_delivery if s not in scenario_deliveries)

            for scenario_delivery in scenario_deliveries:
                if safe_get(scenario_definition_delivery.get(scenario_delivery), CONF_ENABLED, True):
                    self.delivery_by_scenario[scenario_name].append(scenario_delivery)

                scenario_delivery_config = safe_get(scenario_definition_delivery.get(scenario_delivery), CONF_DATA, {})

                # extract message and title templates per scenario per delivery
                for template_field in SCENARIO_TEMPLATE_ATTRS:
                    template_format = scenario_delivery_config.get(template_field)
                    if template_format is not None:
                        self.content_scenario_templates.setdefault(template_field, {})
                        self.content_scenario_templates[template_field].setdefault(scenario_delivery, [])
                        self.content_scenario_templates[template_field][scenario_delivery].append(scenario_name)

        self.delivery_by_scenario[SCENARIO_DEFAULT] = list(default_deliveries.keys())
        if default_scenario:
            for d, dc in self.deliveries.items():
                if dc.get(CONF_ENABLED, True) and d not in self.delivery_by_scenario[SCENARIO_DEFAULT]:
                    self.delivery_by_scenario[SCENARIO_DEFAULT].append(d)

    async def _register_delivery_methods(
        self,
        delivery_methods: list[DeliveryMethod] | None = None,
        delivery_method_classes: list[type[DeliveryMethod]] | None = None,
    ) -> None:
        """Use configure_for_tests() to set delivery_methods to mocks or manually created fixtures"""
        if delivery_methods:
            for delivery_method in delivery_methods:
                self.methods[delivery_method.method] = delivery_method
                await self.methods[delivery_method.method].initialize()
                self.deliveries.update(self.methods[delivery_method.method].valid_deliveries)
        if delivery_method_classes and self.hass:
            for delivery_method_class in delivery_method_classes:
                method_config = self._method_configs.get(delivery_method_class.method, {})
                self.methods[delivery_method_class.method] = delivery_method_class(
                    self.hass,
                    self,
                    self._deliveries,
                    default=method_config.get(CONF_DEFAULT, {}),
                    device_domain=method_config.get(CONF_DEVICE_DOMAIN, []),
                    device_discovery=method_config.get(CONF_DEVICE_DISCOVERY, False),
                    targets_required=method_config.get(CONF_TARGETS_REQUIRED, False),
                )
                await self.methods[delivery_method_class.method].initialize()
                self.deliveries.update(self.methods[delivery_method_class.method].valid_deliveries)

        _LOGGER.info("SUPERNOTIFY configured deliveries %s", "; ".join(self.deliveries.keys()))

    def delivery_method(self, delivery: str) -> DeliveryMethod:
        method_name = self.deliveries.get(delivery, {}).get(CONF_METHOD)
        method: DeliveryMethod | None = self.methods.get(method_name)
        if not method:
            raise ValueError(f"SUPERNOTIFY No method {method_name} for delivery {delivery}")
        return method

    def discover_devices(self, discover_domain: str) -> list[DeviceEntry]:
        devices: list[DeviceEntry] = []
        dev_reg: DeviceRegistry | None = self.device_registry()
        if dev_reg is None:
            _LOGGER.warning(f"SUPERNOTIFY Unable to discover devices for {discover_domain} - no device registry found")
            return []

        all_devs = enabled_devs = found_devs = 0
        for dev in dev_reg.devices.values():
            all_devs += 1
            if not dev.disabled:
                enabled_devs += 1
                for identifier in dev.identifiers:
                    if identifier and len(identifier) > 1 and identifier[0] == discover_domain:
                        _LOGGER.debug("SUPERNOTIFY discovered device %s for identifier %s", dev.name, identifier)
                        devices.append(dev)
                        found_devs += 1
                    elif identifier and len(identifier) != 2:
                        # HomeKit has triples for identifiers, other domains may behave similarly
                        _LOGGER.debug("SUPERNOTIFY Unexpected device %s identifier: %s", dev.name, identifier)  # type: ignore
        _LOGGER.info(
            f"SUPERNOTIFY {discover_domain} device discovery, all={all_devs}, enabled={enabled_devs}, found={found_devs}"
        )
        return devices

    def setup_people(self, recipients: list[dict[str, Any]] | tuple[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        people: dict[str, dict[str, Any]] = {}
        for r in recipients:
            if r.get(CONF_MOBILE_DISCOVERY):
                r[CONF_MOBILE_DEVICES].extend(self.mobile_devices_for_person(r[CONF_PERSON]))
                if r.get(CONF_MOBILE_DEVICES):
                    _LOGGER.info("SUPERNOTIFY Auto configured %s for mobile devices %s", r[CONF_PERSON], r[CONF_MOBILE_DEVICES])
                else:
                    _LOGGER.warning("SUPERNOTIFY Unable to find mobile devices for %s", r[CONF_PERSON])
            if self.hass:
                state: State | None = self.hass.states.get(r[CONF_PERSON])
                if state is not None:
                    r[ATTR_USER_ID] = state.attributes.get(ATTR_USER_ID)
            people[r[CONF_PERSON]] = r
        return people

    def people_state(self) -> list[dict[str, Any]]:
        results = []
        if self.hass:
            for person, person_config in self.people.items():
                # TODO: possibly rate limit this
                try:
                    tracker = self.hass.states.get(person)
                    if tracker is None:
                        person_config[ATTR_STATE] = None
                    else:
                        person_config[ATTR_STATE] = tracker.state
                except Exception as e:
                    _LOGGER.warning("SUPERNOTIFY Unable to determine occupied status for %s: %s", person, e)
                results.append(person_config)
        return results

    def determine_occupancy(self) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {STATE_HOME: [], STATE_NOT_HOME: []}
        for person_config in self.people_state():
            if person_config.get(ATTR_STATE) in (None, STATE_HOME):
                # default to at home if unknown tracker
                results[STATE_HOME].append(person_config)
            else:
                results[STATE_NOT_HOME].append(person_config)
        return results

    def entity_registry(self) -> entity_registry.EntityRegistry | None:
        """Hass entity registry is weird, every component ends up creating its own, with a store, subscribing
        to all entities, so do it once here
        """  # noqa: D205
        if self._entity_registry is not None:
            return self._entity_registry
        if self.hass:
            try:
                self._entity_registry = entity_registry.async_get(self.hass)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to get entity registry: %s", e)
        return self._entity_registry

    def device_registry(self) -> device_registry.DeviceRegistry | None:
        """Hass device registry is weird, every component ends up creating its own, with a store, subscribing
        to all devices, so do it once here
        """  # noqa: D205
        if self._device_registry is not None:
            return self._device_registry
        if self.hass:
            try:
                self._device_registry = device_registry.async_get(self.hass)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to get device registry: %s", e)
        return self._device_registry

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
        person_state = self.hass.states.get(person_entity_id) if self.hass else None
        if not person_state:
            _LOGGER.warning("SUPERNOTIFY Unable to resolve %s", person_entity_id)
        else:
            ent_reg = self.entity_registry()
            dev_reg = self.device_registry()
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
                            if (
                                validate_targets
                                and self.hass
                                and self.hass.services
                                and not self.hass.services.has_service("notify", notify_action)
                            ):
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
