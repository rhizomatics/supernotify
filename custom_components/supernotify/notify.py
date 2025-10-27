"""Supernotify service, extending BaseNotificationService"""

import datetime as dt
import json
import logging
from dataclasses import asdict
from traceback import format_exception
from typing import Any

from cachetools import TTLCache
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.const import CONF_CONDITION, EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.helpers.condition import async_validate_condition_config
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from custom_components.supernotify.archive import ARCHIVE_PURGE_MIN_INTERVAL
from custom_components.supernotify.delivery_method import DeliveryMethod

from . import (
    ATTR_ACTION,
    ATTR_DATA,
    ATTR_DUPE_POLICY_MTSLP,
    ATTR_DUPE_POLICY_NONE,
    CONF_ACTION_GROUPS,
    CONF_ACTIONS,
    CONF_ARCHIVE,
    CONF_CAMERAS,
    CONF_DELIVERY,
    CONF_DUPE_CHECK,
    CONF_DUPE_POLICY,
    CONF_HOUSEKEEPING,
    CONF_HOUSEKEEPING_TIME,
    CONF_LINKS,
    CONF_MEDIA_PATH,
    CONF_METHODS,
    CONF_RECIPIENTS,
    CONF_SCENARIOS,
    CONF_SIZE,
    CONF_TEMPLATE_PATH,
    CONF_TTL,
    DOMAIN,
    PLATFORMS,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    ConditionVariables,
)
from . import SUPERNOTIFY_SCHEMA as PLATFORM_SCHEMA
from .configuration import Context
from .methods.alexa_devices import AlexaDevicesDeliveryMethod
from .methods.alexa_media_player import AlexaMediaPlayerDeliveryMethod
from .methods.chime import ChimeDeliveryMethod
from .methods.email import EmailDeliveryMethod
from .methods.generic import GenericDeliveryMethod
from .methods.media_player_image import MediaPlayerImageDeliveryMethod
from .methods.mobile_push import MobilePushDeliveryMethod
from .methods.persistent import PersistentDeliveryMethod
from .methods.sms import SMSDeliveryMethod
from .notification import Notification

_LOGGER = logging.getLogger(__name__)

SNOOZE_TIME = 60 * 60  # TODO: move to configuration

METHODS: list[type[DeliveryMethod]] = [
    EmailDeliveryMethod,
    SMSDeliveryMethod,
    AlexaDevicesDeliveryMethod,
    AlexaMediaPlayerDeliveryMethod,
    MobilePushDeliveryMethod,
    MediaPlayerImageDeliveryMethod,
    ChimeDeliveryMethod,
    PersistentDeliveryMethod,
    GenericDeliveryMethod,
]  # No auto-discovery of method plugins so manual class registration required here


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> "SuperNotificationAction":
    """Notify specific component setup - see async_setup_legacy in BaseNotificationService"""
    _ = PLATFORM_SCHEMA  # schema must be imported even if not used for HA platform detection
    _ = discovery_info
    for delivery in config.get(CONF_DELIVERY, {}).values():
        if delivery and CONF_CONDITION in delivery:
            try:
                await async_validate_condition_config(hass, delivery[CONF_CONDITION])
            except Exception as e:
                _LOGGER.error("SUPERNOTIFY delivery %s fails condition: %s", delivery[CONF_CONDITION], e)
                raise

    hass.states.async_set(
        f"{DOMAIN}.configured",
        "True",
        {
            CONF_DELIVERY: config.get(CONF_DELIVERY, {}),
            CONF_LINKS: config.get(CONF_LINKS, ()),
            CONF_TEMPLATE_PATH: config.get(CONF_TEMPLATE_PATH, None),
            CONF_MEDIA_PATH: config.get(CONF_MEDIA_PATH, None),
            CONF_ARCHIVE: config.get(CONF_ARCHIVE, {}),
            CONF_RECIPIENTS: config.get(CONF_RECIPIENTS, ()),
            CONF_ACTIONS: config.get(CONF_ACTIONS, {}),
            CONF_HOUSEKEEPING: config.get(CONF_HOUSEKEEPING, {}),
            CONF_ACTION_GROUPS: config.get(CONF_ACTION_GROUPS, {}),
            CONF_SCENARIOS: list(config.get(CONF_SCENARIOS, {}).keys()),
            CONF_METHODS: config.get(CONF_METHODS, {}),
            CONF_CAMERAS: config.get(CONF_CAMERAS, {}),
            CONF_DUPE_CHECK: config.get(CONF_DUPE_CHECK, {}),
        },
    )
    hass.states.async_set(f"{DOMAIN}.failures", "0")
    hass.states.async_set(f"{DOMAIN}.sent", "0")

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    service = SuperNotificationAction(
        hass,
        deliveries=config[CONF_DELIVERY],
        template_path=config[CONF_TEMPLATE_PATH],
        media_path=config[CONF_MEDIA_PATH],
        archive=config[CONF_ARCHIVE],
        housekeeping=config[CONF_HOUSEKEEPING],
        recipients=config[CONF_RECIPIENTS],
        mobile_actions=config[CONF_ACTION_GROUPS],
        scenarios=config[CONF_SCENARIOS],
        links=config[CONF_LINKS],
        method_configs=config[CONF_METHODS],
        cameras=config[CONF_CAMERAS],
        dupe_check=config[CONF_DUPE_CHECK],
    )
    await service.initialize()

    def supplemental_action_refresh_entities(_call: ServiceCall) -> None:
        return service.expose_entities()

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

    def supplemental_action_enquire_people(_call: ServiceCall) -> dict[str, Any]:
        return {"people": service.enquire_people()}

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
        "enquire_people",
        supplemental_action_enquire_people,
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
        "refresh_entities",
        supplemental_action_refresh_entities,
        supports_response=SupportsResponse.NONE,
    )

    return service


class SuperNotificationAction(BaseNotificationService):
    """Implement SuperNotification action."""

    def __init__(
        self,
        hass: HomeAssistant,
        deliveries: dict[str, dict[str, Any]] | None = None,
        template_path: str | None = None,
        media_path: str | None = None,
        archive: dict[str, Any] | None = None,
        housekeeping: dict[str, Any] | None = None,
        recipients: list[dict[str, Any]] | None = None,
        mobile_actions: dict[str, Any] | None = None,
        scenarios: dict[str, dict[str, Any]] | None = None,
        links: list[str] | None = None,
        method_configs: dict[str, Any] | None = None,
        cameras: list[dict[str, Any]] | None = None,
        dupe_check: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the service."""
        self.hass: HomeAssistant = hass
        self.last_notification: Notification | None = None
        self.failures: int = 0
        self.housekeeping: dict[str, Any] = housekeeping or {}
        self.sent: int = 0
        self.context = Context(
            hass,
            deliveries,
            links or [],
            recipients or [],
            mobile_actions,
            template_path,
            media_path,
            archive,
            scenarios,
            method_configs or {},
            cameras,
            METHODS,
        )
        self.unsubscribes: list[CALLBACK_TYPE] = []
        self.dupe_check_config: dict[str, Any] = dupe_check or {}
        self.last_purge: dt.datetime | None = None
        self.notification_cache: TTLCache[tuple[int, str], str] = TTLCache(
            maxsize=self.dupe_check_config.get(CONF_SIZE, 100), ttl=self.dupe_check_config.get(CONF_TTL, 120)
        )

    async def initialize(self) -> None:
        await self.context.initialize()

        self.expose_entities()
        self.unsubscribes.append(self.hass.bus.async_listen("mobile_app_notification_action", self.on_mobile_action))
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

    def expose_entities(self) -> None:
        for scenario in self.context.scenarios.values():
            self.hass.states.async_set(
                f"{DOMAIN}.scenario_{scenario.name}", STATE_UNKNOWN, scenario.attributes(include_condition=False)
            )
        for method in self.context.methods.values():
            self.hass.states.async_set(
                f"{DOMAIN}.method_{method.method}",
                STATE_ON if len(method.valid_deliveries) > 0 else STATE_OFF,
                method.attributes(),
            )
        for delivery_name, delivery in self.context._deliveries.items():
            self.hass.states.async_set(
                f"{DOMAIN}.delivery_{delivery_name}",
                STATE_ON if str(delivery_name in self.context.deliveries) else STATE_OFF,
                delivery,
            )

    def dupe_check(self, notification: Notification) -> bool:
        policy = self.dupe_check_config.get(CONF_DUPE_POLICY, ATTR_DUPE_POLICY_MTSLP)
        if policy == ATTR_DUPE_POLICY_NONE:
            return False
        notification_hash = notification.hash()
        if notification.priority in PRIORITY_VALUES:
            same_or_higher_priority = PRIORITY_VALUES[PRIORITY_VALUES.index(notification.priority) :]
        else:
            same_or_higher_priority = [notification.priority]
        dupe = False
        if any((notification_hash, p) in self.notification_cache for p in same_or_higher_priority):
            _LOGGER.debug("SUPERNOTIFY Detected dupe notification")
            dupe = True
        self.notification_cache[notification_hash, notification.priority] = notification.id
        return dupe

    async def async_send_message(
        self, message: str = "", title: str | None = None, target: list[str] | str | None = None, **kwargs: Any
    ) -> None:
        """Send a message via chosen method."""
        data = kwargs.get(ATTR_DATA, {})
        notification = None
        _LOGGER.debug("Message: %s, target: %s, data: %s", message, target, data)

        try:
            notification = Notification(self.context, message, title, target, data)
            await notification.initialize()
            if self.dupe_check(notification):
                notification.suppress()
            else:
                if await notification.deliver():
                    self.sent += 1
                    self.hass.states.async_set(f"{DOMAIN}.sent", str(self.sent))
                elif notification.errored:
                    _LOGGER.error("SUPERNOTIFY Failed to deliver %s, error count %s", notification.id, notification.errored)
                else:
                    _LOGGER.warning("SUPERNOTIFY No delivery selected for  %s", notification.id)

        except Exception as err:
            # fault barrier of last resort, integration failures should be caught within envelope delivery
            _LOGGER.exception("SUPERNOTIFY Failed to send message %s", message)
            self.failures += 1
            if notification is not None:
                notification.delivery_error = format_exception(err)
            self.hass.states.async_set(f"{DOMAIN}.failures", str(self.failures))

        if notification is not None:
            self.last_notification = notification
            self.context.archive.archive(notification)
            if self.context.archive_topic:
                await self.context.archive_topic.publish(notification)

            _LOGGER.debug(
                "SUPERNOTIFY %s deliveries, %s errors, %s skipped",
                notification.delivered,
                notification.errored,
                notification.skipped,
            )

    def enquire_deliveries_by_scenario(self) -> dict[str, list[str]]:
        return self.context.delivery_by_scenario

    async def enquire_occupancy(self) -> dict[str, list[dict[str, Any]]]:
        return self.context.determine_occupancy()

    async def enquire_active_scenarios(self) -> list[str]:
        occupiers: dict[str, list[dict[str, Any]]] = self.context.determine_occupancy()
        cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, occupiers, None, None)
        return [s.name for s in self.context.scenarios.values() if await s.evaluate(cvars)]

    async def trace_active_scenarios(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        occupiers: dict[str, list[dict[str, Any]]] = self.context.determine_occupancy()
        cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, occupiers, None, None)

        def safe_json(v: Any) -> Any:
            return json.loads(json.dumps(v, cls=ExtendedJSONEncoder))

        enabled = []
        disabled = []
        dcvars = asdict(cvars)
        for s in self.context.scenarios.values():
            if await s.trace(cvars):
                enabled.append(safe_json(s.attributes(include_trace=True)))
            else:
                disabled.append(safe_json(s.attributes(include_trace=True)))
        return enabled, disabled, dcvars

    def enquire_scenarios(self) -> dict[str, dict[str, Any]]:
        return {s.name: s.attributes(include_condition=False) for s in self.context.scenarios.values()}

    def enquire_snoozes(self) -> list[dict[str, Any]]:
        return self.context.snoozer.export()

    def clear_snoozes(self) -> int:
        return self.context.snoozer.clear()

    def enquire_people(self) -> list[dict[str, Any]]:
        return list(self.context.people.values())

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
        self.context.snoozer.handle_command_event(event, self.context.people)

    @callback
    async def async_nightly_tasks(self, now: dt.datetime) -> None:
        _LOGGER.info("SUPERNOTIFY Housekeeping starting as scheduled at %s", now)
        await self.context.archive.cleanup()
        self.context.snoozer.purge_snoozes()
        _LOGGER.info("SUPERNOTIFY Housekeeping completed")
