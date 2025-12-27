"""Supernotify service, extending BaseNotificationService"""

import datetime as dt
import json
import logging
from dataclasses import asdict
from traceback import format_exception
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON, STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    ATTR_ACTION,
    ATTR_DATA,
    CONF_ACTION_GROUPS,
    CONF_ACTIONS,
    CONF_ARCHIVE,
    CONF_CAMERAS,
    CONF_DELIVERY,
    CONF_DUPE_CHECK,
    CONF_HOUSEKEEPING,
    CONF_HOUSEKEEPING_TIME,
    CONF_LINKS,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_MOBILE_DISCOVERY,
    CONF_RECIPIENTS,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SCENARIOS,
    CONF_TEMPLATE_PATH,
    CONF_TRANSPORTS,
    DOMAIN,
    PLATFORMS,
    PRIORITY_MEDIUM,
)
from . import SUPERNOTIFY_SCHEMA as PLATFORM_SCHEMA
from .archive import ARCHIVE_PURGE_MIN_INTERVAL, NotificationArchive
from .common import DupeChecker
from .context import Context
from .delivery import DeliveryRegistry
from .hass_api import HomeAssistantAPI
from .media_grab import MediaStorage
from .model import ConditionVariables, SuppressionReason
from .notification import Notification
from .people import PeopleRegistry, Recipient
from .scenario import ScenarioRegistry
from .snoozer import Snoozer
from .transport import Transport
from .transports.alexa_devices import AlexaDevicesTransport
from .transports.alexa_media_player import AlexaMediaPlayerTransport
from .transports.chime import ChimeTransport
from .transports.email import EmailTransport
from .transports.generic import GenericTransport
from .transports.media_player import MediaPlayerTransport
from .transports.mobile_push import MobilePushTransport
from .transports.mqtt import MQTTTransport
from .transports.notify_entity import NotifyEntityTransport
from .transports.persistent import PersistentTransport
from .transports.sms import SMSTransport
from .transports.tts import TTSTransport

if TYPE_CHECKING:
    from .scenario import Scenario

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

SNOOZE_TIME = 60 * 60  # TODO: move to configuration

TRANSPORTS: list[type[Transport]] = [
    EmailTransport,
    SMSTransport,
    MQTTTransport,
    AlexaDevicesTransport,
    AlexaMediaPlayerTransport,
    MobilePushTransport,
    MediaPlayerTransport,
    ChimeTransport,
    PersistentTransport,
    GenericTransport,
    TTSTransport,
    NotifyEntityTransport,
]  # No auto-discovery of transport plugins so manual class registration required here


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> "SupernotifyAction":
    """Notify specific component setup - see async_setup_legacy in legacy BaseNotificationService"""
    _ = PLATFORM_SCHEMA  # schema must be imported even if not used for HA platform detection
    _ = discovery_info
    # for delivery in config.get(CONF_DELIVERY, {}).values():
    #    if delivery and CONF_CONDITION in delivery:
    #        try:
    #            await async_validate_condition_config(hass, delivery[CONF_CONDITION])
    #        except Exception as e:
    #            _LOGGER.error("SUPERNOTIFY delivery %s fails condition: %s", delivery[CONF_CONDITION], e)
    #            raise

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    service = SupernotifyAction(
        hass,
        deliveries=config[CONF_DELIVERY],
        template_path=config[CONF_TEMPLATE_PATH],
        media_path=config[CONF_MEDIA_PATH],
        archive=config[CONF_ARCHIVE],
        housekeeping=config[CONF_HOUSEKEEPING],
        mobile_discovery=config[CONF_MOBILE_DISCOVERY],
        recipients_discovery=config[CONF_RECIPIENTS_DISCOVERY],
        recipients=config[CONF_RECIPIENTS],
        mobile_actions=config[CONF_ACTION_GROUPS],
        scenarios=config[CONF_SCENARIOS],
        links=config[CONF_LINKS],
        transport_configs=config[CONF_TRANSPORTS],
        cameras=config[CONF_CAMERAS],
        dupe_check=config[CONF_DUPE_CHECK],
    )
    await service.initialize()

    def supplemental_action_enquire_configuration(_call: ServiceCall) -> dict[str, Any]:
        return {
            CONF_DELIVERY: config.get(CONF_DELIVERY, {}),
            CONF_LINKS: config.get(CONF_LINKS, ()),
            CONF_TEMPLATE_PATH: config.get(CONF_TEMPLATE_PATH, None),
            CONF_MEDIA_PATH: config.get(CONF_MEDIA_PATH, None),
            CONF_ARCHIVE: config.get(CONF_ARCHIVE, {}),
            CONF_MOBILE_DISCOVERY: config.get(CONF_MOBILE_DISCOVERY, ()),
            CONF_RECIPIENTS_DISCOVERY: config.get(CONF_RECIPIENTS_DISCOVERY, ()),
            CONF_RECIPIENTS: config.get(CONF_RECIPIENTS, ()),
            CONF_ACTIONS: config.get(CONF_ACTIONS, {}),
            CONF_HOUSEKEEPING: config.get(CONF_HOUSEKEEPING, {}),
            CONF_ACTION_GROUPS: config.get(CONF_ACTION_GROUPS, {}),
            CONF_SCENARIOS: list(config.get(CONF_SCENARIOS, {}).keys()),
            CONF_TRANSPORTS: config.get(CONF_TRANSPORTS, {}),
            CONF_CAMERAS: config.get(CONF_CAMERAS, {}),
            CONF_DUPE_CHECK: config.get(CONF_DUPE_CHECK, {}),
        }

    def supplemental_action_refresh_entities(_call: ServiceCall) -> None:
        return service.expose_entities()

    def supplemental_action_enquire_implicit_deliveries(_call: ServiceCall) -> dict[str, Any]:
        return service.enquire_implicit_deliveries()

    def supplemental_action_enquire_deliveries_by_scenario(_call: ServiceCall) -> dict[str, Any]:
        return service.enquire_deliveries_by_scenario()

    def supplemental_action_enquire_last_notification(_call: ServiceCall) -> dict[str, Any]:
        return service.last_notification.contents() if service.last_notification else {}

    async def supplemental_action_enquire_active_scenarios(call: ServiceCall) -> dict[str, Any]:
        trace = call.data.get("trace", False)
        result: dict[str, Any] = {"scenarios": await service.enquire_active_scenarios()}
        if trace:
            result["trace"] = await service.trace_active_scenarios()
        return result

    def supplemental_action_enquire_scenarios(_call: ServiceCall) -> dict[str, Any]:
        return {"scenarios": service.enquire_scenarios()}

    async def supplemental_action_enquire_occupancy(_call: ServiceCall) -> dict[str, Any]:
        return {"scenarios": await service.enquire_occupancy()}

    def supplemental_action_enquire_snoozes(_call: ServiceCall) -> dict[str, Any]:
        return {"snoozes": service.enquire_snoozes()}

    def supplemental_action_clear_snoozes(_call: ServiceCall) -> dict[str, Any]:
        return {"cleared": service.clear_snoozes()}

    def supplemental_action_enquire_recipients(_call: ServiceCall) -> dict[str, Any]:
        return {"recipients": service.enquire_recipients()}

    async def supplemental_action_purge_archive(call: ServiceCall) -> dict[str, Any]:
        days = call.data.get("days")
        if not service.context.archive.enabled:
            return {"error": "No archive configured"}
        purged = await service.context.archive.cleanup(days=days, force=True)
        arch_size = await service.context.archive.size()
        return {
            "purged": purged,
            "remaining": arch_size,
            "interval": ARCHIVE_PURGE_MIN_INTERVAL,
            "days": service.context.archive.archive_days if days is None else days,
        }

    async def supplemental_action_purge_media(call: ServiceCall) -> dict[str, Any]:
        days = call.data.get("days")
        if not service.context.media_storage.media_path:
            return {"error": "No media storage configured"}
        purged = await service.context.media_storage.cleanup(days=days, force=True)
        size = await service.context.media_storage.size()
        return {
            "purged": purged,
            "remaining": size,
            "interval": service.context.media_storage.purge_minute_interval,
            "days": service.context.media_storage.days if days is None else days,
        }

    hass.services.async_register(
        DOMAIN,
        "enquire_configuration",
        supplemental_action_enquire_configuration,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_implicit_deliveries",
        supplemental_action_enquire_implicit_deliveries,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_deliveries_by_scenario",
        supplemental_action_enquire_deliveries_by_scenario,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_last_notification",
        supplemental_action_enquire_last_notification,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_active_scenarios",
        supplemental_action_enquire_active_scenarios,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_scenarios",
        supplemental_action_enquire_scenarios,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_occupancy",
        supplemental_action_enquire_occupancy,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_recipients",
        supplemental_action_enquire_recipients,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_snoozes",
        supplemental_action_enquire_snoozes,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "clear_snoozes",
        supplemental_action_clear_snoozes,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "purge_archive",
        supplemental_action_purge_archive,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "purge_media",
        supplemental_action_purge_media,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "refresh_entities",
        supplemental_action_refresh_entities,
        supports_response=SupportsResponse.NONE,
    )

    return service


class SupernotifyEntity(NotifyEntity):
    """Implement supernotify as a NotifyEntity platform."""

    _attr_has_entity_name = True
    _attr_name = "supernotify"

    def __init__(
        self,
        unique_id: str,
        platform: "SupernotifyAction",
    ) -> None:
        """Initialize the SuperNotify entity."""
        self._attr_unique_id = unique_id
        self._attr_supported_features = NotifyEntityFeature.TITLE
        self._platform = platform

    async def async_send_message(
        self, message: str, title: str | None = None, target: str | list[str] | None = None, data: dict[str, Any] | None = None
    ) -> None:
        """Send a message to a user."""
        await self._platform.async_send_message(message, title=title, target=target, data=data)


class SupernotifyAction(BaseNotificationService):
    """Implement SuperNotify Action"""

    def __init__(
        self,
        hass: HomeAssistant,
        deliveries: dict[str, dict[str, Any]] | None = None,
        template_path: str | None = None,
        media_path: str | None = None,
        archive: dict[str, Any] | None = None,
        housekeeping: dict[str, Any] | None = None,
        recipients_discovery: bool = True,
        mobile_discovery: bool = True,
        recipients: list[dict[str, Any]] | None = None,
        mobile_actions: dict[str, Any] | None = None,
        scenarios: dict[str, dict[str, Any]] | None = None,
        links: list[str] | None = None,
        transport_configs: dict[str, Any] | None = None,
        cameras: list[dict[str, Any]] | None = None,
        dupe_check: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the service."""
        self.last_notification: Notification | None = None
        self.failures: int = 0
        self.housekeeping: dict[str, Any] = housekeeping or {}
        self.sent: int = 0
        hass_api = HomeAssistantAPI(hass)
        self.context = Context(
            hass_api,
            PeopleRegistry(recipients or [], hass_api, discover=recipients_discovery, mobile_discovery=mobile_discovery),
            ScenarioRegistry(scenarios or {}),
            DeliveryRegistry(deliveries or {}, transport_configs or {}, TRANSPORTS),
            DupeChecker(dupe_check or {}),
            NotificationArchive(archive or {}, hass_api),
            MediaStorage(media_path, self.housekeeping.get(CONF_MEDIA_STORAGE_DAYS, 7)),
            Snoozer(),
            links or [],
            recipients or [],
            mobile_actions,
            template_path,
            cameras=cameras,
        )

        self.exposed_entities: list[str] = []

    async def initialize(self) -> None:
        await self.context.initialize()
        self.context.hass_api.initialize()
        self.context.people_registry.initialize()
        await self.context.delivery_registry.initialize(self.context)
        await self.context.scenario_registry.initialize(
            self.context.delivery_registry,
            self.context.mobile_actions,
            self.context.hass_api,
        )
        await self.context.archive.initialize()
        await self.context.media_storage.initialize(self.context.hass_api)

        self.expose_entities()
        self.context.hass_api.subscribe_event("mobile_app_notification_action", self.on_mobile_action)
        self.context.hass_api.subscribe_state(self.exposed_entities, self._entity_state_change_listener)

        housekeeping_schedule = self.housekeeping.get(CONF_HOUSEKEEPING_TIME)
        if housekeeping_schedule:
            _LOGGER.info("SUPERNOTIFY setting up housekeeping schedule at: %s", housekeeping_schedule)
            self.context.hass_api.subscribe_time(
                housekeeping_schedule.hour, housekeeping_schedule.minute, housekeeping_schedule.second, self.async_nightly_tasks
            )

        self.context.hass_api.subscribe_event(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)

    async def async_shutdown(self, event: Event) -> None:
        _LOGGER.info("SUPERNOTIFY shutting down, %s (%s)", event.event_type, event.time_fired)
        self.shutdown()

    async def async_unregister_services(self) -> None:
        _LOGGER.info("SUPERNOTIFY unregistering")
        self.shutdown()
        return await super().async_unregister_services()

    def shutdown(self) -> None:
        self.context.hass_api.disconnect()
        _LOGGER.info("SUPERNOTIFY shut down")

    async def async_send_message(
        self, message: str = "", title: str | None = None, target: list[str] | str | None = None, **kwargs: Any
    ) -> None:
        """Send a message via chosen transport."""
        data = kwargs.get(ATTR_DATA, {})
        notification = None
        _LOGGER.debug("Message: %s, target: %s, data: %s", message, target, data)

        try:
            notification = Notification(self.context, message, title, target, data)
            await notification.initialize()
            if await notification.deliver():
                self.sent += 1
                self.context.hass_api.set_state(f"sensor.{DOMAIN}_notifications", self.sent)
            elif notification.failed:
                _LOGGER.error("SUPERNOTIFY Failed to deliver %s, error count %s", notification.id, notification.error_count)
            else:
                if notification.delivered == 0:
                    codes: list[SuppressionReason] = notification._skip_reasons
                    reason: str = ",".join(str(code) for code in codes)
                    problem: bool = codes != [SuppressionReason.DUPE]
                else:
                    problem = True
                    reason = "No delivery envelopes generated"
                if problem:
                    _LOGGER.warning("SUPERNOTIFY No deliveries made for %s: %s", notification.id, reason)
                else:
                    _LOGGER.debug("SUPERNOTIFY Deliveries suppressed for %s: %s", notification.id, reason)

        except Exception as err:
            # fault barrier of last resort, integration failures should be caught within envelope delivery
            _LOGGER.exception("SUPERNOTIFY Failed to send message %s", message)
            self.failures += 1
            if notification is not None:
                notification._delivery_error = format_exception(err)
            self.context.hass_api.set_state(f"sensor.{DOMAIN}_failures", self.failures)

        if notification is None:
            _LOGGER.warning("SUPERNOTIFY NULL Notification, %s", message)
        else:
            self.last_notification = notification
            await self.context.archive.archive(notification)
            _LOGGER.debug(
                "SUPERNOTIFY %s deliveries, %s failed, %s skipped, % suppressed",
                notification.delivered,
                notification.failed,
                notification.skipped,
                notification.suppressed,
            )

    async def _entity_state_change_listener(self, event: Event[EventStateChangedData]) -> None:
        changes = 0
        if event is not None:
            _LOGGER.info(f"SUPERNOTIFY {event.event_type} event for entity: {event.data}")
            new_state: State | None = event.data["new_state"]
            if new_state and event.data["entity_id"].startswith(f"binary_sensor.{DOMAIN}_scenario_"):
                scenario: Scenario | None = self.context.scenario_registry.scenarios.get(
                    event.data["entity_id"].replace(f"binary_sensor.{DOMAIN}_scenario_", "")
                )
                if scenario is None:
                    _LOGGER.warning(f"SUPERNOTIFY Event for unknown scenario {event.data['entity_id']}")
                else:
                    if new_state.state == "off" and scenario.enabled:
                        scenario.enabled = False
                        _LOGGER.info(f"SUPERNOTIFY Disabling scenario {scenario.name}")
                        changes += 1
                    elif new_state.state == "on" and not scenario.enabled:
                        scenario.enabled = True
                        _LOGGER.info(f"SUPERNOTIFY Enabling scenario {scenario.name}")
                        changes += 1
                    else:
                        _LOGGER.info(f"SUPERNOTIFY No change to scenario {scenario.name}, already {new_state}")
            elif new_state and event.data["entity_id"].startswith(f"binary_sensor.{DOMAIN}_delivery_"):
                delivery_name: str = event.data["entity_id"].replace(f"binary_sensor.{DOMAIN}_delivery_", "")
                if new_state.state == "off":
                    if self.context.delivery_registry.disable(delivery_name):
                        changes += 1
                elif new_state.state == "on":
                    if self.context.delivery_registry.enable(delivery_name):
                        changes += 1
                else:
                    _LOGGER.info(f"SUPERNOTIFY No change to delivery {delivery_name} for state {new_state.state}")
            elif new_state and event.data["entity_id"].startswith(f"binary_sensor.{DOMAIN}_transport_"):
                transport: Transport | None = self.context.delivery_registry.transports.get(
                    event.data["entity_id"].replace(f"binary_sensor.{DOMAIN}_transport_", "")
                )
                if transport is None:
                    _LOGGER.warning(f"SUPERNOTIFY Event for unknown transport {event.data['entity_id']}")
                else:
                    if new_state.state == "off" and transport.enabled:
                        transport.enabled = False
                        _LOGGER.info(f"SUPERNOTIFY Disabling transport {transport.name}")
                        changes += 1
                    elif new_state.state == "on" and not transport.enabled:
                        transport.enabled = True
                        _LOGGER.info(f"SUPERNOTIFY Enabling transport {transport.name}")
                        changes += 1
                    else:
                        _LOGGER.info(f"SUPERNOTIFY No change to transport {transport.name}, already {new_state}")
            elif new_state and event.data["entity_id"].startswith(f"binary_sensor.{DOMAIN}_recipient_"):
                recipient: Recipient | None = self.context.people_registry.people.get(
                    event.data["entity_id"].replace(f"binary_sensor.{DOMAIN}_recipient_", "person.")
                )
                if recipient is None:
                    _LOGGER.warning(f"SUPERNOTIFY Event for unknown recipient {event.data['entity_id']}")
                else:
                    if new_state.state == "off" and recipient.enabled:
                        recipient.enabled = False
                        _LOGGER.info(f"SUPERNOTIFY Disabling recipient {recipient.entity_id}")
                        changes += 1
                    elif new_state.state == "on" and not recipient.enabled:
                        recipient.enabled = True
                        _LOGGER.info(f"SUPERNOTIFY Enabling recipient {recipient.entity_id}")
                        changes += 1
                    else:
                        _LOGGER.info(f"SUPERNOTIFY No change to recipient {recipient.entity_id}, already {new_state}")

            else:
                _LOGGER.warning("SUPERNOTIFY entity event with nothing to do:%s", event)

    def expose_entity(
        self,
        entity_name: str,
        state: str,
        attributes: dict[str, Any],
        platform: str = Platform.BINARY_SENSOR,
        original_name: str | None = None,
        original_icon: str | None = None,
        entity_registry: er.EntityRegistry | None = None,
    ) -> None:
        """Expose a technical entity in Home Assistant representing internal state and attributes"""
        entity_id: str
        if entity_registry is not None:
            try:
                entry: er.RegistryEntry = entity_registry.async_get_or_create(
                    platform,
                    DOMAIN,
                    entity_name,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    original_name=original_name,
                    original_icon=original_icon,
                )
                entity_id = entry.entity_id
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to register entity %s: %s", entity_name, e)
                # continue anyway even if not registered as state is independent of entity
                entity_id = f"{platform}.{DOMAIN}_{entity_name}"
        try:
            self.context.hass_api.set_state(entity_id, state, attributes)
            self.exposed_entities.append(entity_id)
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Unable to set state for entity %s: %s", entity_id, e)

    def expose_entities(self) -> None:
        # Create on the fly entities for key internal config and state
        ent_reg: er.EntityRegistry | None = self.context.hass_api.entity_registry()
        if ent_reg is None:
            _LOGGER.error("SUPERNOTIFY Unable to access entity registry to expose entities")
            return

        self.context.hass_api.set_state(f"sensor.{DOMAIN}_failures", self.failures)
        self.context.hass_api.set_state(f"sensor.{DOMAIN}_notifications", self.sent)

        for scenario in self.context.scenario_registry.scenarios.values():
            self.expose_entity(
                f"scenario_{scenario.name}",
                state=STATE_UNKNOWN,
                attributes=scenario.attributes(include_condition=False),
                original_name=f"{scenario.name} Scenario",
                original_icon="mdi:assignment",
                entity_registry=ent_reg,
            )
        for transport in self.context.delivery_registry.transports.values():
            self.expose_entity(
                f"transport_{transport.name}",
                state=STATE_ON if transport.enabled else STATE_OFF,
                attributes=transport.attributes(),
                original_name=f"{transport.name} Transport Adaptor",
                original_icon="mdi:delivery-truck-speed",
                entity_registry=ent_reg,
            )

        for delivery in self.context.delivery_registry.deliveries.values():
            self.expose_entity(
                f"delivery_{delivery.name}",
                state=STATE_ON if delivery.enabled else STATE_OFF,
                attributes=delivery.attributes(),
                original_name=f"{delivery.name} Delivery Configuration",
                original_icon="mdi:package_2",
                entity_registry=ent_reg,
            )

        for recipient in self.context.people_registry.people.values():
            self.expose_entity(
                f"recipient_{recipient.name}",
                state=STATE_ON if recipient.enabled else STATE_OFF,
                attributes=recipient.attributes(),
                original_name=f"{recipient.name}",
                original_icon="mdi:inbox_text_person",
                entity_registry=ent_reg,
            )

    def enquire_implicit_deliveries(self) -> dict[str, Any]:
        v: dict[str, list[str]] = {}
        for t in self.context.delivery_registry.transports:
            for d in self.context.delivery_registry.implicit_deliveries:
                if d.transport.name == t:
                    v.setdefault(t, [])
                    v[t].append(d.name)
        return v

    def enquire_deliveries_by_scenario(self) -> dict[str, dict[str, list[str]]]:
        return {
            name: {
                "enabled": scenario.enabling_deliveries(),
                "disabled": scenario.disabling_deliveries(),
                "applies": scenario.relevant_deliveries(),
            }
            for name, scenario in self.context.scenario_registry.scenarios.items()
            if scenario.enabled
        }

    async def enquire_occupancy(self) -> dict[str, list[dict[str, Any]]]:
        occupancy = self.context.people_registry.determine_occupancy()
        return {k: [v.as_dict() for v in vs] for k, vs in occupancy.items()}

    async def enquire_active_scenarios(self) -> list[str]:
        occupiers: dict[str, list[Recipient]] = self.context.people_registry.determine_occupancy()
        cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, occupiers, None, None)
        return [s.name for s in self.context.scenario_registry.scenarios.values() if s.evaluate(cvars)]

    async def trace_active_scenarios(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        occupiers: dict[str, list[Recipient]] = self.context.people_registry.determine_occupancy()
        cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, occupiers, None, None)

        def safe_json(v: Any) -> Any:
            return json.loads(json.dumps(v, cls=ExtendedJSONEncoder))

        enabled = []
        disabled = []
        dcvars = asdict(cvars)
        for s in self.context.scenario_registry.scenarios.values():
            if await s.trace(cvars):
                enabled.append(safe_json(s.attributes(include_trace=True)))
            else:
                disabled.append(safe_json(s.attributes(include_trace=True)))
        return enabled, disabled, dcvars

    def enquire_scenarios(self) -> dict[str, dict[str, Any]]:
        return {s.name: s.attributes(include_condition=False) for s in self.context.scenario_registry.scenarios.values()}

    def enquire_snoozes(self) -> list[dict[str, Any]]:
        return self.context.snoozer.export()

    def clear_snoozes(self) -> int:
        return self.context.snoozer.clear()

    def enquire_recipients(self) -> list[dict[str, Any]]:
        return [p.as_dict() for p in self.context.people_registry.people.values()]

    @callback
    def on_mobile_action(self, event: Event) -> None:
        """Listen for mobile actions relevant to snooze and silence notifications

        Example Action:
        event_type: mobile_app_notification_action
        data:
            foo: a
        origin: REMOTE
        time_fired: "2024-04-20T13:14:09.360708+00:00"
        context:
            id: 01HVXT93JGWEDW0KE57Z0X6Z1K
            parent_id: null
            user_id: e9dbae1a5abf44dbbad52ff85501bb17
        """
        event_name = event.data.get(ATTR_ACTION)
        if event_name is None or not event_name.startswith("SUPERNOTIFY_"):
            return  # event not intended for here
        self.context.snoozer.handle_command_event(event, self.context.people_registry.enabled_recipients())

    @callback
    async def async_nightly_tasks(self, now: dt.datetime) -> None:
        _LOGGER.info("SUPERNOTIFY Housekeeping starting as scheduled at %s", now)
        await self.context.archive.cleanup()
        self.context.snoozer.purge_snoozes()
        await self.context.media_storage.cleanup()
        _LOGGER.info("SUPERNOTIFY Housekeeping completed")
