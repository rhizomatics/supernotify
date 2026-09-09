"""Supernotify service, extending BaseNotificationService"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from traceback import format_exception
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    Context as HAContext,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN
from .archive import NotificationArchive
from .common import DupeChecker
from .const import (
    ATTR_ACTION,
    ATTR_DATA,
    CONF_ACTION_GROUPS,
    CONF_ARCHIVE,
    CONF_CAMERAS,
    CONF_DELIVERY,
    CONF_DUPE_CHECK,
    CONF_HOUSEKEEPING,
    CONF_HOUSEKEEPING_TIME,
    CONF_LINKS,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_MEDIA_URL_PREFIX,
    CONF_MOBILE_DISCOVERY,
    CONF_RECIPIENTS,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SCENARIO_CONTROL,
    CONF_SCENARIOS,
    CONF_SNOOZE,
    CONF_TEMPLATE_PATH,
    CONF_TRANSPORTS,
    PRIORITY_MEDIUM,
)
from .context import Context
from .delivery import DeliveryRegistry
from .hass_api import HomeAssistantAPI
from .media_grab import MediaStorage
from .model import ConditionVariables, SuppressionReason
from .notification import Notification
from .people import PeopleRegistry, Recipient
from .scenario import ScenarioRegistry
from .snoozer import Snoozer
from .transports.alexa_devices import AlexaDevicesTransport
from .transports.alexa_media_player import AlexaMediaPlayerTransport
from .transports.chime import ChimeTransport
from .transports.discord import DiscordTransport
from .transports.email import EmailTransport
from .transports.generic import GenericTransport
from .transports.gotify import GotifyTransport
from .transports.html5 import HTML5Transport
from .transports.kodi import KodiTransport
from .transports.lametric import LaMetricTransport
from .transports.matrix import MatrixTransport
from .transports.media_player import MediaPlayerTransport
from .transports.mobile_push import MobilePushTransport
from .transports.mqtt import MQTTTransport
from .transports.notify_entity import NotifyEntityTransport
from .transports.ntfy import NtfyTransport
from .transports.persistent import PersistentTransport
from .transports.pushover import PushoverTransport
from .transports.sms import SMSTransport
from .transports.telegram import TelegramTransport
from .transports.tts import TTSTransport

if TYPE_CHECKING:
    import datetime as dt

    from .sensor import SupernotifyCounterSensor
    from .transport import Transport

_LOGGER = logging.getLogger(__name__)

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
    NtfyTransport,
    GotifyTransport,
    TelegramTransport,
    LaMetricTransport,
    PushoverTransport,
    HTML5Transport,
    MatrixTransport,
    KodiTransport,
    DiscordTransport,
]  # No auto-discovery of transport plugins so manual class registration required here


class SupernotifyEngine:
    """Owns the Context/registries/transports and actually delivers notifications.

    This is the shared engine behind every entrypoint - notify.supernotify (via the
    SuperNotificationService legacy shim), supernotify.notify, and the NotifyEntity platform
    (RecipientNotifyEntity) - so it deliberately has no dependency on
    BaseNotificationService or anything else specific to the legacy notify platform. If/when
    HA core drops BaseNotificationService, only SuperNotificationService and its wiring in
    __init__.py need to go; this class and everything else built on it are unaffected.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        deliveries: dict[str, dict[str, Any]] | None = None,
        template_path: str | None = None,
        media_path: str | None = None,
        media_url_prefix: str | None = None,
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
        snooze: dict[str, Any] | None = None,
        scenario_control: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the service."""
        self.last_notification: Notification | None = None
        self.failures: int = 0
        self.housekeeping: dict[str, Any] = housekeeping or {}
        self.sent: int = 0
        # Set by sensor.py's async_setup_entry once the sensor platform has loaded; None until
        # then (e.g. during initialize(), and in tests that build SupernotifyEngine directly
        # without a config entry) - see restore_sent/restore_failures and expose_entities().
        self._notifications_entity: SupernotifyCounterSensor | None = None
        self._failures_entity: SupernotifyCounterSensor | None = None
        hass_api = HomeAssistantAPI(hass)

        people_registry = PeopleRegistry(
            recipients or [], hass_api, discover=recipients_discovery, mobile_discovery=mobile_discovery
        )
        self.context = Context(
            hass_api,
            people_registry,
            ScenarioRegistry(scenarios or {}, scenario_control, people_registry),
            DeliveryRegistry(deliveries or {}, transport_configs or {}, TRANSPORTS),
            DupeChecker(dupe_check or {}),
            NotificationArchive(archive or {}, hass_api),
            MediaStorage(
                media_path,
                media_url_prefix=media_url_prefix,
                days=self.housekeeping.get(CONF_MEDIA_STORAGE_DAYS, 7),
            ),
            Snoozer(snooze),
            links or [],
            recipients or [],
            mobile_actions,
            template_path,
            cameras=cameras,
        )

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
        await self.context.snoozer.initialize(self.context.hass_api)

        # Delivery/transport binary_sensors are still raw hass_api.expose_entity() writes (a
        # separate, larger conversion - see issue #175); scenario/recipient binary_sensors and
        # the counters are real entities now and self-initialize when their platforms load
        # (after this method returns - see __init__.py), so expose_entities() itself is only
        # needed on demand (supernotify.refresh_entities), not eagerly here.
        self.context.delivery_registry.expose_entities(self.context.hass_api)
        self.context.hass_api.subscribe_event("mobile_app_notification_action", self.on_mobile_action)

        # Entities to watch for an external toggle (Developer Tools, an automation) via
        # _entity_state_change_listener below. Delivery/transport entity_ids come from
        # hass_api.exposed_entities (populated by expose_entity() just above); scenario and
        # recipient entity_ids are computed directly since those are real entities that never
        # call expose_entity() - see binary_sensor.py for the same entity_id scheme.
        watched_entities = [
            *self.context.hass_api.exposed_entities,
            *(f"binary_sensor.{DOMAIN}_scenario_{name}" for name in self.context.scenario_registry.scenarios),
            *(f"binary_sensor.{DOMAIN}_recipient_{r.name}" for r in self.context.people_registry.people.values()),
        ]
        self.context.hass_api.subscribe_state(watched_entities, self._entity_state_change_listener)

        housekeeping_schedule = self.housekeeping.get(CONF_HOUSEKEEPING_TIME)
        if housekeeping_schedule:
            _LOGGER.info("SUPERNOTIFY Setting up housekeeping schedule at: %s", housekeeping_schedule)
            self.context.hass_api.subscribe_time(
                housekeeping_schedule.hour, housekeeping_schedule.minute, housekeeping_schedule.second, self.async_nightly_tasks
            )
        else:
            _LOGGER.info(
                "SUPERNOTIFY Housekeeping disabled. Storage must be manually managed if using attachments or image snapshots"
            )

        self.context.hass_api.subscribe_event(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)

    async def async_shutdown(self, event: Event) -> None:
        _LOGGER.info("SUPERNOTIFY Shutting down, %s (%s)", event.event_type, event.time_fired)
        self.shutdown()

    def shutdown(self) -> None:
        self.context.hass_api.disconnect()
        _LOGGER.info("SUPERNOTIFY Shut down")

    async def async_send_message(
        self,
        message: str = "",
        title: str | None = None,
        target: list[str] | str | dict[str, Any] | None = None,
        context: HAContext | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a message via chosen transport."""
        data = kwargs.get(ATTR_DATA, {})
        notification = None
        _LOGGER.debug("SUPERNOTIFY Message: %s, target: %s, data: %s", message, target, data)

        if context is None:
            # only reachable when async_send_message is invoked directly rather than via a
            # registered action (e.g. SuperNotificationService._async_notify_message_service, or
            # supernotify.notify in async_setup_supplemental_actions) - without this fallback,
            # downstream service calls for this notification would each get their own
            # unrelated Context, leaving them unlinked in the logbook/recorder
            _LOGGER.debug("SUPERNOTIFY No context supplied, generating new one")
            context = HAContext()

        try:
            notification = Notification(self.context, message, title, target, action_data=data, ha_context=context)
            await notification.initialize()
            if await notification.deliver():
                self.sent += 1
                if self._notifications_entity is not None:
                    self._notifications_entity.set_value(self.sent)
                else:
                    self.context.hass_api.set_state(f"sensor.{DOMAIN}_notifications", self.sent, context=context)
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
            if self._failures_entity is not None:
                self._failures_entity.set_value(self.failures)
            else:
                self.context.hass_api.set_state(f"sensor.{DOMAIN}_failures", self.failures, context=context)

        if notification is None:
            _LOGGER.warning("SUPERNOTIFY NULL Notification, %s", message)
        else:
            self.last_notification = notification
            await self.context.archive.archive(notification)
            _LOGGER.debug(
                "SUPERNOTIFY %s deliveries, %s failed, %s skipped, %s suppressed",
                notification.delivered,
                notification.failed,
                notification.skipped,
                notification.suppressed,
            )

    async def _entity_state_change_listener(self, event: Event[EventStateChangedData]) -> None:
        if event is None:
            return
        _LOGGER.debug(f"SUPERNOTIFY {event.event_type} event for entity: {event.data}")
        new_state: State | None = event.data["new_state"]
        if new_state is None:
            return

        entity_id: str = event.data["entity_id"]
        for registry in (
            self.context.scenario_registry,
            self.context.delivery_registry,
            self.context.people_registry,
        ):
            if registry.handle_entity_state_change(entity_id, new_state) is not None:
                return
        _LOGGER.warning("SUPERNOTIFY entity event with nothing to do:%s", event)

    def restore_sent(self, value: int) -> None:
        """Called once by SupernotifyCounterSensor.async_added_to_hass() with the value
        restored from the last run, so the in-memory counter and the displayed one agree.

        max() guards against a notification landing on the pre-restore fallback counter (see
        async_send_message's hass_api.set_state() branch) during the window between
        async_register_services() and the sensor platform finishing its restore - without it,
        a restore arriving after such an increment would silently overwrite the higher,
        already-correct value with the older persisted one."""
        self.sent = max(self.sent, value)

    def restore_failures(self, value: int) -> None:
        """Called once by SupernotifyCounterSensor.async_added_to_hass() with the value
        restored from the last run, so the in-memory counter and the displayed one agree.

        See restore_sent() for why max() and not a plain assignment."""
        self.failures = max(self.failures, value)

    def expose_entities(self) -> None:
        """Refresh every entity SuperNotify exposes for introspection/control.

        Scenario and recipient binary_sensors, and the notification/failure counters, are real
        platform entities (binary_sensor.py/sensor.py) added via async_forward_entry_setups and
        keep themselves current; refreshing them here is a safe no-op before those platforms
        have loaded (e.g. during initialize(), and in tests that build SupernotifyEngine
        directly without a config entry - see the entity-less fallbacks below and in
        async_send_message). Delivery/transport entities are still raw hass_api writes, pending
        a separate, larger conversion to switch entities (see issue #175).
        """
        if self._notifications_entity is not None:
            self._notifications_entity.set_value(self.sent)
        else:
            self.context.hass_api.set_state(f"sensor.{DOMAIN}_notifications", self.sent)
        if self._failures_entity is not None:
            self._failures_entity.set_value(self.failures)
        else:
            self.context.hass_api.set_state(f"sensor.{DOMAIN}_failures", self.failures)

        self.context.scenario_registry.async_refresh_scenario_states()
        for entity in self.context.people_registry.recipient_entities():
            entity.async_write_ha_state()
        self.context.delivery_registry.expose_entities(self.context.hass_api)

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

        def safe_json(v: Any) -> Any:  # ruff: ignore[any-type]
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
            user_id: a9dbae1a5abf33dbbad52ff82201bb17
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


def build_supernotify_engine(hass: HomeAssistant, config: ConfigType) -> SupernotifyEngine:
    """Construct a SupernotifyEngine from a fully validated FULL_CONFIG_SCHEMA config dict.

    Used by the config-entry setup (async_setup_entry in __init__.py), the sole owner of
    registering notify.supernotify.
    """
    return SupernotifyEngine(
        hass,
        deliveries=config[CONF_DELIVERY],
        template_path=config[CONF_TEMPLATE_PATH],
        media_path=config[CONF_MEDIA_PATH],
        media_url_prefix=config.get(CONF_MEDIA_URL_PREFIX),
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
        snooze=config[CONF_SNOOZE],
        scenario_control=config.get(CONF_SCENARIO_CONTROL),
    )
