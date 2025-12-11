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
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from custom_components.supernotify.archive import ARCHIVE_PURGE_MIN_INTERVAL
from custom_components.supernotify.transport import Transport

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
from .archive import NotificationArchive
from .common import DupeChecker
from .context import Context
from .delivery import DeliveryRegistry
from .hass_api import HomeAssistantAPI
from .media_grab import MediaStorage
from .model import ConditionVariables
from .notification import Notification
from .people import PeopleRegistry, Recipient
from .scenario import ScenarioRegistry
from .snoozer import Snoozer
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

if TYPE_CHECKING:
    from custom_components.supernotify.delivery import Delivery

    from .scenario import Scenario


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

    hass.states.async_set(
        f"{DOMAIN}.configured",
        "True",
        {
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
        },
    )
    hass.states.async_set(f"{DOMAIN}.failures", "0")
    hass.states.async_set(f"{DOMAIN}.sent", "0")

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
        self.hass: HomeAssistant = hass
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

        self.unsubscribes: list[CALLBACK_TYPE] = []
        self.exposed_entities: list[str] = []

    async def initialize(self) -> None:
        await self.context.initialize()
        self.context.hass_api.initialize()
        self.context.people_registry.initialize()
        await self.context.delivery_registry.initialize(self.context)
        await self.context.scenario_registry.initialize(
            self.context.delivery_registry.deliveries,
            self.context.mobile_actions,
            self.context.hass_api,
        )
        await self.context.archive.initialize()
        await self.context.media_storage.initialize(self.context.hass_api)

        self.expose_entities()
        self.unsubscribes.append(self.hass.bus.async_listen("mobile_app_notification_action", self.on_mobile_action))
        self.unsubscribes.append(
            async_track_state_change_event(self.hass, self.exposed_entities, self._entity_state_change_listener)
        )

        housekeeping_schedule = self.housekeeping.get(CONF_HOUSEKEEPING_TIME)
        if housekeeping_schedule:
            _LOGGER.info("SUPERNOTIFY setting up housekeeping schedule at: %s", housekeeping_schedule)
            self.unsubscribes.append(
                async_track_time_change(
                    self.hass,
                    self.async_nightly_tasks,
                    hour=housekeeping_schedule.hour,
                    minute=housekeeping_schedule.minute,
                    second=housekeeping_schedule.second,
                )
            )

        self.unsubscribes.append(self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.async_shutdown))

    async def async_shutdown(self, event: Event) -> None:
        _LOGGER.info("SUPERNOTIFY shutting down, %s", event)
        self.shutdown()

    async def async_unregister_services(self) -> None:
        _LOGGER.info("SUPERNOTIFY unregistering")
        self.shutdown()
        return await super().async_unregister_services()

    def shutdown(self) -> None:
        for unsub in self.unsubscribes:
            try:
                _LOGGER.debug("SUPERNOTIFY unsubscribing: %s", unsub)
                unsub()
            except Exception as e:
                _LOGGER.error("SUPERNOTIFY failed to unsubscribe: %s", e)
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
                self.hass.states.async_set(f"{DOMAIN}.sent", str(self.sent))
            elif notification.errored:
                _LOGGER.error("SUPERNOTIFY Failed to deliver %s, error count %s", notification.id, notification.errored)
            else:
                _LOGGER.warning("SUPERNOTIFY No deliveries made for  %s", notification.id)

        except Exception as err:
            # fault barrier of last resort, integration failures should be caught within envelope delivery
            _LOGGER.exception("SUPERNOTIFY Failed to send message %s", message)
            self.failures += 1
            if notification is not None:
                notification.delivery_error = format_exception(err)
            self.hass.states.async_set(f"{DOMAIN}.failures", str(self.failures))

        if notification is not None:
            self.last_notification = notification
            await self.context.archive.archive(notification)
            _LOGGER.debug(
                "SUPERNOTIFY %s deliveries, %s errors, %s skipped",
                notification.delivered,
                notification.errored,
                notification.skipped,
            )

    async def _entity_state_change_listener(self, event: Event[EventStateChangedData]) -> None:
        changes = 0
        if event is not None:
            _LOGGER.info(f"SUPERNOTIFY {event.event_type} event for entity: {event.data}")
            new_state: State | None = event.data["new_state"]
            if new_state and event.data["entity_id"].startswith(f"{DOMAIN}.scenario_"):
                scenario: Scenario | None = self.context.scenario_registry.scenarios.get(
                    event.data["entity_id"].replace(f"{DOMAIN}.scenario_", "")
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
            elif new_state and event.data["entity_id"].startswith(f"{DOMAIN}.delivery_"):
                delivery_config: Delivery | None = self.context.delivery_registry.deliveries.get(
                    event.data["entity_id"].replace(f"{DOMAIN}.delivery_", "")
                )
                if delivery_config is None:
                    _LOGGER.warning(f"SUPERNOTIFY Event for unknown delivery {event.data['entity_id']}")
                else:
                    if new_state.state == "off" and delivery_config.enabled:
                        delivery_config.enabled = False
                        _LOGGER.info(f"SUPERNOTIFY Disabling delivery {delivery_config.name}")
                        changes += 1
                    elif new_state.state == "on" and not delivery_config.enabled:
                        delivery_config.enabled = True
                        _LOGGER.info(f"SUPERNOTIFY Enabling delivery {delivery_config.name}")
                        changes += 1
                    else:
                        _LOGGER.info(f"SUPERNOTIFY No change to delivery {delivery_config.name}, already {new_state}")
            elif new_state and event.data["entity_id"].startswith(f"{DOMAIN}.transport_"):
                transport: Transport | None = self.context.delivery_registry.transports.get(
                    event.data["entity_id"].replace(f"{DOMAIN}.transport_", "")
                )
                if transport is None:
                    _LOGGER.warning(f"SUPERNOTIFY Event for unknown transport {event.data['entity_id']}")
                else:
                    if new_state.state == "off" and transport.override_enabled:
                        transport.override_enabled = False
                        _LOGGER.info(f"SUPERNOTIFY Disabling transport {transport.name}")
                        changes += 1
                    elif new_state.state == "on" and not transport.override_enabled:
                        transport.override_enabled = True
                        _LOGGER.info(f"SUPERNOTIFY Enabling transport {transport.name}")
                        changes += 1
                    else:
                        _LOGGER.info(f"SUPERNOTIFY No change to transport {transport.name}, already {new_state}")
            elif new_state and event.data["entity_id"].startswith(f"{DOMAIN}.recipient_"):
                recipient: Recipient | None = self.context.people_registry.people.get(
                    event.data["entity_id"].replace(f"{DOMAIN}.recipient_", "person.")
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

    def expose_entities(self) -> None:
        # Create on the fly entities for key internal config and state

        for scenario in self.context.scenario_registry.scenarios.values():
            self.hass.states.async_set(
                f"{DOMAIN}.scenario_{scenario.name}", STATE_UNKNOWN, scenario.attributes(include_condition=False)
            )
            self.exposed_entities.append(f"{DOMAIN}.scenario_{scenario.name}")
        for transport in self.context.delivery_registry.transports.values():
            self.hass.states.async_set(
                f"{DOMAIN}.transport_{transport.name}",
                STATE_ON if transport.override_enabled else STATE_OFF,
                transport.attributes(),
            )
            self.exposed_entities.append(f"{DOMAIN}.transport_{transport.name}")
        for delivery_name, delivery in self.context.delivery_registry.deliveries.items():
            self.hass.states.async_set(
                f"{DOMAIN}.delivery_{delivery.name}", STATE_ON if delivery.enabled else STATE_OFF, delivery.attributes()
            )
            self.exposed_entities.append(f"{DOMAIN}.delivery_{delivery_name}")
        for recipient in self.context.people_registry.people.values():
            self.hass.states.async_set(
                f"{DOMAIN}.{recipient.name}", STATE_ON if recipient.enabled else STATE_OFF, recipient.attributes()
            )
            self.exposed_entities.append(f"{DOMAIN}.{recipient.name}")

    def enquire_implicit_deliveries(self) -> dict[str, Any]:
        v: dict[str, list[str]] = {}
        for t in self.context.delivery_registry.transports:
            for d in self.context.delivery_registry.implicit_deliveries:
                if d.transport.name == t:
                    v.setdefault(t, [])
                    v[t].append(d.name)
        return v

    def enquire_deliveries_by_scenario(self) -> dict[str, list[str]]:
        return {
            name: list(scenario.delivery)
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
