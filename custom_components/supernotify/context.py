from __future__ import annotations

import logging
import socket
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ENABLED, CONF_NAME
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.config_validation import boolean
from homeassistant.helpers.network import get_url

from . import (
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_CAMERA,
    CONF_TRANSPORT,
    DOMAIN,
    SELECTION_DEFAULT,
    SELECTION_FALLBACK,
    SELECTION_FALLBACK_ON_ERROR,
)
from .archive import NotificationArchive
from .common import ensure_list
from .model import TransportConfig
from .scenario import ScenarioRegistry
from .snoozer import Snoozer

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.delivery import Delivery
    from custom_components.supernotify.transport import Transport

    from .people import PeopleRegistry

_LOGGER = logging.getLogger(__name__)


class Context:
    def __init__(
        self,
        hass: HomeAssistant | None = None,
        deliveries: ConfigType | None = None,
        links: list[str] | None = None,
        recipients: list[dict[str, Any]] | None = None,
        mobile_actions: ConfigType | None = None,
        template_path: str | None = None,
        media_path: str | None = None,
        archive_config: dict[str, str] | None = None,
        scenarios: ConfigType | None = None,
        transport_configs: ConfigType | None = None,
        cameras: list[ConfigType] | None = None,
        transport_types: list[type[Transport]] | None = None,
        people_registry: PeopleRegistry | None = None,
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

        self.people_registry: PeopleRegistry | None = people_registry
        self.scenario_registry: ScenarioRegistry = ScenarioRegistry(scenarios or {})
        self.links: list[dict[str, Any]] = ensure_list(links)
        # raw configured deliveries
        self._deliveries: ConfigType = deliveries if isinstance(deliveries, dict) else {}
        # validated deliveries
        self.deliveries: dict[str, Delivery] = {}
        self._recipients: list[dict[str, Any]] = ensure_list(recipients)
        self.mobile_actions: ConfigType = mobile_actions or {}
        self.template_path: Path | None = Path(template_path) if template_path else None
        self.media_path: Path | None = Path(media_path) if media_path else None
        archive_config = archive_config or {}
        self.archive: NotificationArchive = NotificationArchive(
            self.hass,
            bool(archive_config.get(CONF_ENABLED, False)),
            archive_config.get(CONF_ARCHIVE_PATH),
            archive_config.get(CONF_ARCHIVE_DAYS),
            mqtt_topic=archive_config.get(CONF_ARCHIVE_MQTT_TOPIC),
            mqtt_qos=int(archive_config.get(CONF_ARCHIVE_MQTT_QOS, 0)),
            mqtt_retain=boolean(archive_config.get(CONF_ARCHIVE_MQTT_RETAIN, True)),
        )

        self.cameras: dict[str, Any] = {c[CONF_CAMERA]: c for c in cameras} if cameras else {}
        self.transports: dict[str, Transport] = {}
        self._transport_configs: dict[str, TransportConfig] = (
            {n: TransportConfig(n, c) for n, c in transport_configs.items()} if transport_configs else {}
        )

        self._fallback_on_error: list[Delivery] = []
        self._fallback_by_default: list[Delivery] = []
        self._default_deliveries: list[Delivery] = []
        self._entity_registry: entity_registry.EntityRegistry | None = None
        self._device_registry: device_registry.DeviceRegistry | None = None
        self._transport_types: list[type[Transport]] = transport_types or []
        self.snoozer = Snoozer()
        # test harness support
        self._transport_instancess: list[Transport] | None = None

    async def initialize(self) -> None:
        await self._register_delivery_transports(
            delivery_transports=self._transport_instancess, transport_classes=self._transport_types
        )

        if self.template_path and not self.template_path.exists():
            _LOGGER.warning("SUPERNOTIFY template path not found at %s", self.template_path)
            self.template_path = None

        if self.media_path and not self.media_path.exists():
            _LOGGER.info("SUPERNOTIFY media path not found at %s", self.media_path)
            try:
                self.media_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY media path %s cannot be created: %s", self.media_path, e)
                await self.raise_issue("media_path", "media_path", {"path": str(self.media_path), "error": str(e)})
                self.media_path = None
        if self.media_path is not None:
            _LOGGER.info("SUPERNOTIFY abs media path: %s", self.media_path.absolute())
        if self.archive:
            await self.archive.initialize()

        self.initialize_deliveries()

    def configure_for_tests(
        self, transport_instancess: list[Transport] | None = None, create_default_scenario: bool = False
    ) -> None:
        self.scenario_registry.default_scenario_for_testing = create_default_scenario
        self._transport_instancess = transport_instancess

    async def raise_issue(
        self,
        issue_id: str,
        issue_key: str,
        issue_map: dict[str, str],
        severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
        learn_more_url: str = "https://supernotify.rhizomatics.github.io",
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

    def initialize_deliveries(self) -> None:
        for delivery in self.deliveries.values():
            if delivery.enabled:
                if SELECTION_FALLBACK_ON_ERROR in delivery.selection:
                    self._fallback_on_error.append(delivery)
                if SELECTION_FALLBACK in delivery.selection:
                    self._fallback_by_default.append(delivery)
                if SELECTION_DEFAULT in delivery.selection:
                    self._default_deliveries.append(delivery)

    @property
    def fallback_by_default_deliveries(self) -> list[Delivery]:
        return [d for d in self._fallback_by_default if d.enabled]

    @property
    def fallback_on_error_deliveries(self) -> list[Delivery]:
        return [d for d in self._fallback_on_error if d.enabled]

    @property
    def default_deliveries(self) -> list[Delivery]:
        """Deliveries switched on all the time for implicit selection"""
        return [d for d in self._default_deliveries if d.enabled]

    async def _register_delivery_transports(
        self,
        delivery_transports: list[Transport] | None = None,
        transport_classes: list[type[Transport]] | None = None,
    ) -> None:
        """Use configure_for_tests() to set delivery_transports to mocks or manually created fixtures"""
        if delivery_transports:
            for transport in delivery_transports:
                self.transports[transport.transport] = transport
                await self.transports[transport.transport].initialize()
                self.deliveries.update(self.transports[transport.transport].valid_deliveries)
        if transport_classes and self.hass and self.people_registry:
            for transport_class in transport_classes:
                transport_config: TransportConfig = self._transport_configs.get(
                    transport_class.transport, TransportConfig(transport_class.transport, {})
                )
                self.transports[transport_class.transport] = transport_class(
                    self.hass,
                    self,
                    self.people_registry,
                    {d: dc for d, dc in self._deliveries.items() if dc.get(CONF_TRANSPORT) == transport_class.transport},
                    delivery_defaults=transport_config.delivery_defaults,
                    enabled=transport_config.enabled,
                    device_domain=transport_config.device_domain,
                    device_discovery=transport_config.device_discovery,
                    target_required=transport_config.target_required,
                )
                await self.transports[transport_class.transport].initialize()
                self.deliveries.update(self.transports[transport_class.transport].valid_deliveries)

        unconfigured_deliveries = [dc for d, dc in self._deliveries.items() if d not in self.deliveries]
        for bad_del in unconfigured_deliveries:
            # presumably there was no transport for these
            await self.raise_issue(
                f"delivery_{bad_del.get(CONF_NAME)}_for_transport_{bad_del.get(CONF_TRANSPORT)}_failed_to_configure",
                issue_key="delivery_unknown_transport",
                issue_map={"delivery": bad_del.get(CONF_NAME), "transport": bad_del.get(CONF_TRANSPORT)},
            )
        _LOGGER.info("SUPERNOTIFY configured deliveries %s", "; ".join(self.deliveries.keys()))

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
