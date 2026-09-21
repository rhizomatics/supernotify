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
    HomeAssistant,
    callback,
)
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.typing import ConfigType

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
    OVERRIDE_KIND_DELIVERY,
    OVERRIDE_KIND_RECIPIENT,
    OVERRIDE_KIND_SCENARIO,
    OVERRIDE_KIND_TRANSPORT,
    OVERRIDE_KINDS,
    PRIORITY_MEDIUM,
)
from .context import Context
from .delivery import DeliveryRegistry
from .exceptions import UncategorizedTargetError
from .hass_api import HomeAssistantAPI
from .media_grab import MediaStorage
from .model import ConditionVariables, SuppressionReason
from .notification import Notification
from .people import PeopleRegistry, Recipient
from .scenario import ScenarioRegistry
from .sensor import SupernotifyCounterSensor
from .snoozer import Snoozer
from .static_config import TRANSPORTS

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterable

    from .switch import Overridable, SupernotifyOverridableSwitch

_LOGGER = logging.getLogger(__name__)


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
        self.housekeeping: dict[str, Any] = housekeeping or {}
        # The counts live only in these entities, which restore their own value across restarts;
        # sensor.py hands them to Home Assistant once its platform loads
        self.notifications_sensor = SupernotifyCounterSensor("notifications", "notifications")
        self.failures_sensor = SupernotifyCounterSensor("failures", "failures")
        # Every switch overriding a configured enabled flag, by unique_id - populated by switch.py
        # as each is added to Home Assistant
        self.override_switches: dict[str, SupernotifyOverridableSwitch] = {}
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

        # Every entity - switches, binary_sensors and counters - is a real platform entity, added
        # once this method returns (see __init__.py), and keeps its own state current
        self.context.hass_api.subscribe_event("mobile_app_notification_action", self.on_mobile_action)

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

    @property
    def counter_sensors(self) -> list[SupernotifyCounterSensor]:
        return [self.notifications_sensor, self.failures_sensor]

    @property
    def sent(self) -> int:
        return self.notifications_sensor.count

    @property
    def failures(self) -> int:
        return self.failures_sensor.count

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
                self.notifications_sensor.increment()
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
            self.failures_sensor.increment()
            if notification is not None:
                notification._delivery_error = format_exception(err)

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
            if notification.uncategorized_targets:
                # raised only now, at the very end - every target that could be delivered
                # already has been, so one uncategorized target must never get in the way
                # of the rest of the notification going out
                raise UncategorizedTargetError(notification.delivered, notification.uncategorized_targets)

    @callback
    def refresh_entities(self) -> None:
        """Re-publish the current state of every entity SuperNotify provides.

        Entities are only refreshed once added to Home Assistant, so this is a safe no-op for any
        whose platform hasn't loaded (e.g. in tests that build SupernotifyEngine directly without
        a config entry). Must run in the event loop, as it writes entity state.
        """
        self.notifications_sensor.refresh()
        self.failures_sensor.refresh()
        self.context.scenario_registry.async_refresh_scenario_states()
        for entity in self.context.people_registry.recipient_entities():
            entity.async_write_ha_state()
        for legacy_entity in self.context.delivery_registry.legacy_entities():
            legacy_entity.async_write_ha_state()
        for switch in self.override_switches.values():
            switch.async_write_ha_state()

    def _overridables(self, kind: str) -> Iterable[Overridable]:
        overridables: dict[str, Iterable[Overridable]] = {
            OVERRIDE_KIND_SCENARIO: self.context.scenario_registry.scenarios.values(),
            OVERRIDE_KIND_RECIPIENT: self.context.people_registry.people.values(),
            OVERRIDE_KIND_DELIVERY: self.context.delivery_registry.deliveries.values(),
            OVERRIDE_KIND_TRANSPORT: self.context.delivery_registry.transports.values(),
        }
        return overridables[kind]

    @callback
    def reset_overrides(self, kinds: Iterable[str] = OVERRIDE_KINDS) -> dict[str, list[str]]:
        """Put everything switched on or off at runtime back to its configured enabled state,
        returning the names reset for each kind.

        Walks the scenarios, recipients, deliveries and transports themselves rather than their
        switches, so one whose switch is disabled in the entity registry is reset too.
        """
        reset: dict[str, list[str]] = {}
        for kind in kinds:
            names = reset[kind] = []
            for item in self._overridables(kind):
                if item.enabled == item.config_enabled:
                    continue
                switch = self.override_switches.get(f"{kind}_{item.name}")
                if switch is not None:
                    switch.async_set_enabled(item.config_enabled)
                else:
                    item.enabled = item.config_enabled
                    self._async_refresh_related(kind, item.name)
                names.append(item.name)
        return reset

    @callback
    def _async_refresh_related(self, kind: str, name: str) -> None:
        """Re-publish the binary_sensor following the enabled flag of something with no switch
        to do it - the same as that switch's own _refresh_related()."""
        if kind == OVERRIDE_KIND_SCENARIO:
            self.context.scenario_registry.async_refresh_entity(name)
        elif kind == OVERRIDE_KIND_RECIPIENT:
            self.context.people_registry.async_refresh_entity(name)
        else:
            self.context.delivery_registry.async_refresh_entity(f"{kind}_{name}")

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
