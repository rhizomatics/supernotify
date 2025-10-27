import asyncio
import datetime as dt
import logging
import uuid
from pathlib import Path
from traceback import format_exception
from typing import Any

import voluptuous as vol
from homeassistant.components.notify.const import ATTR_DATA, ATTR_TARGET
from homeassistant.const import CONF_ENABLED, CONF_NAME, CONF_TARGET, STATE_HOME, STATE_NOT_HOME
from homeassistant.helpers.template import Template
from jinja2 import TemplateError
from voluptuous import humanize

from custom_components.supernotify import (
    ACTION_DATA_SCHEMA,
    ATTR_ACTION_GROUPS,
    ATTR_ACTIONS,
    ATTR_DEBUG,
    ATTR_DELIVERY,
    ATTR_DELIVERY_SELECTION,
    ATTR_JPEG_OPTS,
    ATTR_MEDIA,
    ATTR_MEDIA_CAMERA_DELAY,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CAMERA_PTZ_PRESET,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_MESSAGE_HTML,
    ATTR_PRIORITY,
    ATTR_RECIPIENTS,
    ATTR_SCENARIOS_APPLY,
    ATTR_SCENARIOS_CONSTRAIN,
    ATTR_SCENARIOS_REQUIRE,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_MESSAGE,
    CONF_OCCUPANCY,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_PRIORITY,
    CONF_PTZ_DELAY,
    CONF_PTZ_METHOD,
    CONF_PTZ_PRESET_DEFAULT,
    CONF_RECIPIENTS,
    CONF_SELECTION,
    CONF_TITLE,
    DELIVERY_SELECTION_EXPLICIT,
    DELIVERY_SELECTION_FIXED,
    DELIVERY_SELECTION_IMPLICIT,
    OCCUPANCY_ALL,
    OCCUPANCY_ALL_IN,
    OCCUPANCY_ALL_OUT,
    OCCUPANCY_ANY_IN,
    OCCUPANCY_ANY_OUT,
    OCCUPANCY_NONE,
    OCCUPANCY_ONLY_IN,
    OCCUPANCY_ONLY_OUT,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    SCENARIO_DEFAULT,
    SCENARIO_NULL,
    SELECTION_BY_SCENARIO,
    STRICT_ACTION_DATA_SCHEMA,
    ConditionVariables,
    MessageOnlyPolicy,
)
from custom_components.supernotify.archive import ArchivableObject
from custom_components.supernotify.common import DebugTrace, safe_extend
from custom_components.supernotify.delivery_method import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    DeliveryMethod,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.scenario import Scenario

from .common import ensure_dict, ensure_list
from .configuration import Context
from .media_grab import move_camera_to_ptz_preset, select_avail_camera, snap_camera, snap_image, snapshot_from_url

_LOGGER = logging.getLogger(__name__)


class Notification(ArchivableObject):
    def __init__(
        self,
        context: Context,
        message: str | None = None,
        title: str | None = None,
        target: list[str] | str | None = None,
        action_data: dict[str, Any] | None = None,
    ) -> None:
        self.created: dt.datetime = dt.datetime.now(tz=dt.UTC)
        self.debug_trace: DebugTrace = DebugTrace(message=message, title=title, data=action_data, target=target)
        self._message: str | None = message
        self.context: Context = context
        action_data = action_data or {}
        self.target: list[str] = ensure_list(target)
        self._title: str | None = title
        self.id = str(uuid.uuid1())
        self.snapshot_image_path: Path | None = None
        self.delivered: int = 0
        self.errored: int = 0
        self.skipped: int = 0
        self.delivered_envelopes: list[Envelope] = []
        self.undelivered_envelopes: list[Envelope] = []
        self.delivery_error: list[str] | None = None

        self.validate_action_data(action_data)
        # for compatibility with other notify calls, pass thru surplus data to underlying delivery methods
        self.data: dict[str, Any] = {k: v for k, v in action_data.items() if k not in STRICT_ACTION_DATA_SCHEMA(action_data)}
        action_data = {k: v for k, v in action_data.items() if k not in self.data}

        self.priority: str = action_data.get(ATTR_PRIORITY, PRIORITY_MEDIUM)
        self.message_html: str | None = action_data.get(ATTR_MESSAGE_HTML)
        self.required_scenario_names: list[str] = ensure_list(action_data.get(ATTR_SCENARIOS_REQUIRE))
        self.applied_scenario_names: list[str] = ensure_list(action_data.get(ATTR_SCENARIOS_APPLY))
        self.constrain_scenario_names: list[str] = ensure_list(action_data.get(ATTR_SCENARIOS_CONSTRAIN))
        self.delivery_selection: str | None = action_data.get(ATTR_DELIVERY_SELECTION)
        self.delivery_overrides_type: str = action_data.get(ATTR_DELIVERY).__class__.__name__
        self.delivery_overrides: dict[str, Any] = ensure_dict(action_data.get(ATTR_DELIVERY))
        self.action_groups: list[str] | None = action_data.get(ATTR_ACTION_GROUPS)
        self.recipients_override: list[str] | None = action_data.get(ATTR_RECIPIENTS)
        self.data.update(action_data.get(ATTR_DATA, {}))
        self.media: dict[str, Any] = action_data.get(ATTR_MEDIA) or {}
        self.debug: bool = action_data.get(ATTR_DEBUG, False)
        self.actions: dict[str, Any] = action_data.get(ATTR_ACTIONS) or {}
        self.delivery_results: dict[str, Any] = {}
        self.delivery_errors: dict[str, Any] = {}

        self.selected_delivery_names: list[str] = []
        self.enabled_scenarios: dict[str, Scenario] = {}
        self.selected_scenario_names: list[str] = []
        self.people_by_occupancy: list[dict[str, Any]] = []
        self.globally_disabled: bool = False
        self.occupancy: dict[str, list[dict[str, Any]]] = {}
        self.condition_variables: ConditionVariables | None = None

    async def initialize(self) -> None:
        """Async post-construction initialization"""
        if self.delivery_selection is None:
            if self.delivery_overrides_type in ("list", "str"):
                # a bare list of deliveries implies intent to restrict
                _LOGGER.debug("SUPERNOTIFY defaulting delivery selection as explicit for type %s", self.delivery_overrides_type)
                self.delivery_selection = DELIVERY_SELECTION_EXPLICIT
            else:
                # whereas a dict may be used to tune or restrict
                self.delivery_selection = DELIVERY_SELECTION_IMPLICIT
                _LOGGER.debug("SUPERNOTIFY defaulting delivery selection as implicit for type %s", self.delivery_overrides_type)

        self.occupancy = self.context.determine_occupancy()
        self.condition_variables = ConditionVariables(
            self.applied_scenario_names,
            self.required_scenario_names,
            self.constrain_scenario_names,
            self.priority,
            self.occupancy,
            self._message,
            self._title,
        )  # requires occupancy first

        enabled_scenario_names: list[str] = list(self.applied_scenario_names) or []
        self.selected_scenario_names = await self.select_scenarios()
        enabled_scenario_names.extend(self.selected_scenario_names)
        if self.constrain_scenario_names:
            enabled_scenario_names = [
                s
                for s in enabled_scenario_names
                if (s in self.constrain_scenario_names or s in self.applied_scenario_names) and s != SCENARIO_NULL
            ]
        if self.required_scenario_names and not any(s in enabled_scenario_names for s in self.required_scenario_names):
            _LOGGER.info("SUPERNOTIFY suppressing notification, no required scenarios enabled")
            self.selected_delivery_names = []
            self.globally_disabled = True
        else:
            for s in enabled_scenario_names:
                scenario_obj = self.context.scenarios.get(s)
                if scenario_obj is not None:
                    self.enabled_scenarios[s] = scenario_obj

            self.selected_delivery_names = self.select_deliveries()
            self.globally_disabled = self.context.snoozer.is_global_snooze(self.priority)
            self.default_media_from_actions()
            self.apply_enabled_scenarios()

    def validate_action_data(self, action_data: dict[str, Any]) -> None:
        if action_data.get(ATTR_PRIORITY) and action_data.get(ATTR_PRIORITY) not in PRIORITY_VALUES:
            _LOGGER.warning("SUPERNOTIFY invalid priority %s - overriding to medium", action_data.get(ATTR_PRIORITY))
            action_data[ATTR_PRIORITY] = PRIORITY_MEDIUM
        try:
            humanize.validate_with_humanized_errors(action_data, ACTION_DATA_SCHEMA)
        except vol.Invalid as e:
            _LOGGER.warning("SUPERNOTIFY invalid service data %s: %s", action_data, e)
            raise

    def apply_enabled_scenarios(self) -> None:
        """Set media and action_groups from scenario if defined, first come first applied"""
        action_groups: list[str] = []
        for scen_obj in self.enabled_scenarios.values():
            if scen_obj.media and not self.media:
                self.media.update(scen_obj.media)
            if scen_obj.action_groups:
                action_groups.extend(ag for ag in scen_obj.action_groups if ag not in action_groups)
        if action_groups:
            self.action_groups = action_groups

    def select_deliveries(self) -> list[str]:
        scenario_enable_deliveries: list[str] = []
        default_enable_deliveries: list[str] = []
        scenario_disable_deliveries: list[str] = []

        if self.delivery_selection != DELIVERY_SELECTION_FIXED:
            for scenario_name in self.enabled_scenarios:
                scenario_enable_deliveries.extend(self.context.delivery_by_scenario.get(scenario_name, ()))
            if self.delivery_selection == DELIVERY_SELECTION_IMPLICIT:
                default_enable_deliveries = self.context.delivery_by_scenario.get(SCENARIO_DEFAULT, [])

        override_enable_deliveries = []
        override_disable_deliveries = []

        for delivery, delivery_override in self.delivery_overrides.items():
            if (delivery_override is None or delivery_override.get(CONF_ENABLED, True)) and delivery in self.context.deliveries:
                override_enable_deliveries.append(delivery)
            elif delivery_override is not None and not delivery_override.get(CONF_ENABLED, True):
                override_disable_deliveries.append(delivery)

        if self.delivery_selection != DELIVERY_SELECTION_FIXED:
            scenario_disable_deliveries = [
                d
                for d, dc in self.context.deliveries.items()
                if dc.get(CONF_SELECTION) == SELECTION_BY_SCENARIO and d not in scenario_enable_deliveries
            ]
        all_enabled = list(set(scenario_enable_deliveries + default_enable_deliveries + override_enable_deliveries))
        all_disabled = scenario_disable_deliveries + override_disable_deliveries
        if self.debug_trace:
            self.debug_trace.delivery_selection["override_disable_deliveries"] = override_disable_deliveries
            self.debug_trace.delivery_selection["override_enable_deliveries"] = override_enable_deliveries
            self.debug_trace.delivery_selection["scenario_enable_deliveries"] = scenario_enable_deliveries
            self.debug_trace.delivery_selection["default_enable_deliveries"] = default_enable_deliveries
            self.debug_trace.delivery_selection["scenario_disable_deliveries"] = scenario_disable_deliveries

        return [d for d in all_enabled if d not in all_disabled]

    def default_media_from_actions(self) -> None:
        """If no media defined, look for iOS / Android actions that have media defined"""
        if self.media:
            return
        if self.data.get("image"):
            self.media[ATTR_MEDIA_SNAPSHOT_URL] = self.data.get("image")
        if self.data.get("video"):
            self.media[ATTR_MEDIA_CLIP_URL] = self.data.get("video")
        if self.data.get("attachment", {}).get("url"):
            url = self.data["attachment"]["url"]
            if url and url.endswith(".mp4") and not self.media.get(ATTR_MEDIA_CLIP_URL):
                self.media[ATTR_MEDIA_CLIP_URL] = url
            elif (
                url
                and (url.endswith(".jpg") or url.endswith(".jpeg") or url.endswith(".png"))
                and not self.media.get(ATTR_MEDIA_SNAPSHOT_URL)
            ):
                self.media[ATTR_MEDIA_SNAPSHOT_URL] = url

    def _render_scenario_templates(
        self, original: str | None, template_field: str, matching_ctx: str, delivery_name: str
    ) -> str | None:
        template_scenario_names = self.context.content_scenario_templates.get(template_field, {}).get(delivery_name, [])
        if not template_scenario_names:
            return original
        context_vars = self.condition_variables.as_dict() if self.condition_variables else {}
        rendered = original if original is not None else ""
        for scen_obj in [obj for name, obj in self.enabled_scenarios.items() if name in template_scenario_names]:
            context_vars[matching_ctx] = rendered
            try:
                template_format = scen_obj.delivery.get(delivery_name, {}).get(CONF_DATA, {}).get(template_field)
                if template_format is not None:
                    template = Template(template_format, self.context.hass)
                    rendered = template.async_render(variables=context_vars)
            except TemplateError as e:
                _LOGGER.warning("SUPERNOTIFY Rendering template %s for %s failed: %s", template_field, delivery_name, e)
        return rendered

    def message(self, delivery_name: str) -> str | None:
        # message and title reverse the usual defaulting, delivery config overrides runtime call
        delivery_config: dict[str, Any] = self.context.deliveries.get(delivery_name, {})
        msg: str | None = delivery_config.get(CONF_MESSAGE, self._message)
        delivery_method: DeliveryMethod = self.context.delivery_method(delivery_name)
        message_usage: str = str(delivery_method.option_str(OPTION_MESSAGE_USAGE, delivery_config))
        if message_usage.upper() == MessageOnlyPolicy.USE_TITLE:
            title = self.title(delivery_name, ignore_usage=True)
            if title:
                msg = title
        elif message_usage.upper() == MessageOnlyPolicy.COMBINE_TITLE:
            title = self.title(delivery_name, ignore_usage=True)
            if title:
                msg = f"{title} {msg}"
        if (
            delivery_method.option_bool(OPTION_SIMPLIFY_TEXT, delivery_config) is True
            or delivery_method.option_bool(OPTION_STRIP_URLS, delivery_config) is True
        ):
            msg = delivery_method.simplify(msg, strip_urls=delivery_method.option_bool(OPTION_STRIP_URLS, delivery_config))

        msg = self._render_scenario_templates(msg, "message_template", "notification_message", delivery_name)
        if msg is None:  # keep mypy happy
            return None
        return str(msg)

    def title(self, delivery_name: str, ignore_usage: bool = False) -> str | None:
        # message and title reverse the usual defaulting, delivery config overrides runtime call
        delivery_config = self.context.deliveries.get(delivery_name, {})
        delivery_method: DeliveryMethod = self.context.delivery_method(delivery_name)
        message_usage = delivery_method.option_str(OPTION_MESSAGE_USAGE, delivery_config)
        if not ignore_usage and message_usage.upper() in (MessageOnlyPolicy.USE_TITLE, MessageOnlyPolicy.COMBINE_TITLE):
            title = None
        else:
            title = delivery_config.get(CONF_TITLE, self._title)
            if (
                delivery_method.option_bool(OPTION_SIMPLIFY_TEXT, delivery_config) is True
                or delivery_method.option_bool(OPTION_STRIP_URLS, delivery_config) is True
            ):
                title = delivery_method.simplify(
                    title, strip_urls=delivery_method.option_bool(OPTION_STRIP_URLS, delivery_config)
                )
            title = self._render_scenario_templates(title, "title_template", "notification_title", delivery_name)
        if title is None:
            return None
        return str(title)

    def suppress(self) -> None:
        self.globally_disabled = True
        _LOGGER.info("SUPERNOTIFY Suppressing notification (%s)", self.id)

    async def deliver(self) -> bool:
        if self.globally_disabled:
            _LOGGER.info("SUPERNOTIFY Suppressing globally silenced/snoozed notification (%s)", self.id)
            self.skipped += 1
            return False

        _LOGGER.debug(
            "Message: %s, notification: %s, deliveries: %s",
            self._message,
            self.id,
            self.selected_delivery_names,
        )

        for delivery in self.selected_delivery_names:
            await self.call_delivery_method(delivery)

        if self.delivered == 0 and self.errored == 0:
            for delivery in self.context.fallback_by_default:
                if delivery not in self.selected_delivery_names:
                    await self.call_delivery_method(delivery)

        if self.delivered == 0 and self.errored > 0:
            for delivery in self.context.fallback_on_error:
                if delivery not in self.selected_delivery_names:
                    await self.call_delivery_method(delivery)

        return self.delivered > 0

    async def call_delivery_method(self, delivery: str) -> None:
        try:
            delivery_method: DeliveryMethod = self.context.delivery_method(delivery)
            delivery_config = delivery_method.delivery_config(delivery)

            delivery_priorities = delivery_config.get(CONF_PRIORITY) or ()
            if self.priority and delivery_priorities and self.priority not in delivery_priorities:
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on priority (%s)", delivery, self.priority)
                self.skipped += 1
                return
            if not await delivery_method.evaluate_delivery_conditions(delivery_config, self.condition_variables):
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on conditions", delivery)
                self.skipped += 1
                return

            recipients = self.generate_recipients(delivery, delivery_method)
            envelopes = self.generate_envelopes(delivery, delivery_method, recipients)
            for envelope in envelopes:
                try:
                    await delivery_method.deliver(envelope)
                    self.delivered += envelope.delivered
                    self.errored += envelope.errored
                    if envelope.delivered:
                        self.delivered_envelopes.append(envelope)
                    else:
                        self.undelivered_envelopes.append(envelope)
                except Exception as e2:
                    _LOGGER.warning("SUPERNOTIFY Failed to deliver %s: %s", envelope.delivery_name, e2)
                    _LOGGER.debug("SUPERNOTIFY %s", e2, exc_info=True)
                    self.errored += 1
                    envelope.delivery_error = format_exception(e2)
                    self.undelivered_envelopes.append(envelope)

        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Failed to notify using %s", delivery)
            _LOGGER.debug("SUPERNOTIFY %s delivery failure", delivery, exc_info=True)
            self.delivery_errors[delivery] = format_exception(e)

    def hash(self) -> int:
        return hash((self._message, self._title))

    def contents(self, minimal: bool = False) -> dict[str, Any]:
        """ArchiveableObject implementation"""
        sanitized = {k: v for k, v in self.__dict__.items() if k not in ("context")}
        sanitized["delivered_envelopes"] = [e.contents(minimal=minimal) for e in self.delivered_envelopes]
        sanitized["undelivered_envelopes"] = [e.contents(minimal=minimal) for e in self.undelivered_envelopes]
        sanitized["enabled_scenarios"] = {k: v.contents(minimal=minimal) for k, v in self.enabled_scenarios.items()}
        if self.debug_trace:
            sanitized["debug_trace"] = self.debug_trace.contents()
        else:
            del sanitized["debug_trace"]
        return sanitized

    def base_filename(self) -> str:
        """ArchiveableObject implementation"""
        return f"{self.created.isoformat()[:16]}_{self.id}"

    def delivery_data(self, delivery_name: str) -> dict[str, Any]:
        delivery_override = self.delivery_overrides.get(delivery_name)
        return delivery_override.get(CONF_DATA) if delivery_override else {}

    def delivery_scenarios(self, delivery_name: str) -> dict[str, Scenario]:
        return {
            s: obj for s, obj in self.enabled_scenarios.items() if delivery_name in self.context.delivery_by_scenario.get(s, [])
        }

    async def select_scenarios(self) -> list[str]:
        return [s.name for s in self.context.scenarios.values() if await s.evaluate(self.condition_variables)]

    def merge(self, attribute: str, delivery_name: str) -> dict[str, Any]:
        delivery: dict[str, Any] = self.delivery_overrides.get(delivery_name, {})
        base: dict[str, Any] = delivery.get(attribute, {})
        for scenario in self.enabled_scenarios.values():
            if scenario and hasattr(scenario, attribute):
                base.update(getattr(scenario, attribute))
        if hasattr(self, attribute):
            base.update(getattr(self, attribute))
        return base

    def record_resolve(self, delivery_name: str, category: str, resolved: str | list[Any] | None) -> None:
        """Debug support for recording detailed target resolution in archived notification"""
        self.debug_trace.resolved.setdefault(delivery_name, {})
        self.debug_trace.resolved[delivery_name].setdefault(category, [])
        if isinstance(resolved, list):
            self.debug_trace.resolved[delivery_name][category].extend(resolved)
        else:
            self.debug_trace.resolved[delivery_name][category].append(resolved)

    def filter_people_by_occupancy(self, occupancy: str) -> list[dict[str, Any]]:
        people = list(self.context.people.values())
        if occupancy == OCCUPANCY_ALL:
            return people
        if occupancy == OCCUPANCY_NONE:
            return []

        away = self.occupancy[STATE_NOT_HOME]
        at_home = self.occupancy[STATE_HOME]
        if occupancy == OCCUPANCY_ALL_IN:
            return people if len(away) == 0 else []
        if occupancy == OCCUPANCY_ALL_OUT:
            return people if len(at_home) == 0 else []
        if occupancy == OCCUPANCY_ANY_IN:
            return people if len(at_home) > 0 else []
        if occupancy == OCCUPANCY_ANY_OUT:
            return people if len(away) > 0 else []
        if occupancy == OCCUPANCY_ONLY_IN:
            return at_home
        if occupancy == OCCUPANCY_ONLY_OUT:
            return away

        _LOGGER.warning("SUPERNOTIFY Unknown occupancy tested: %s", occupancy)
        return []

    def generate_recipients(self, delivery_name: str, delivery_method: DeliveryMethod) -> list[dict[str, Any]]:
        delivery_config: dict[str, Any] = delivery_method.delivery_config(delivery_name)

        recipients: list[dict[str, Any]] = []
        if self.target:
            # first priority is explicit target set on notify call, which overrides everything else
            for t in self.target:
                if t in self.context.people:
                    recipients.append(self.context.people[t])
                    self.record_resolve(
                        delivery_name,
                        "1a_person_target",
                        t,
                    )
                else:
                    recipients.append({ATTR_TARGET: t})
                    self.record_resolve(delivery_name, "1b_non_person_target", t)
            _LOGGER.debug("SUPERNOTIFY %s Overriding with explicit targets: %s", __name__, recipients)
        else:
            # second priority is explicit target on delivery
            if delivery_config and CONF_TARGET in delivery_config and delivery_config[CONF_TARGET]:
                recipients.extend({ATTR_TARGET: e} for e in delivery_config.get(CONF_TARGET, []))
                self.record_resolve(delivery_name, "2b_delivery_config_target", delivery_config.get(CONF_TARGET))
                _LOGGER.debug("SUPERNOTIFY %s Using delivery config targets: %s", __name__, recipients)

            # next priority is explicit recipients on delivery
            if delivery_config and CONF_RECIPIENTS in delivery_config and delivery_config[CONF_RECIPIENTS]:
                recipients.extend(delivery_config[CONF_RECIPIENTS])
                self.record_resolve(delivery_name, "2c_delivery_config_recipient", delivery_config.get(CONF_RECIPIENTS))
                _LOGGER.debug("SUPERNOTIFY %s Using overridden recipients: %s", delivery_name, recipients)

            # If target not specified on service call or delivery, then default to std list of recipients
            elif not delivery_config or CONF_TARGET not in delivery_config:
                recipients = self.filter_people_by_occupancy(delivery_config.get(CONF_OCCUPANCY, OCCUPANCY_ALL))
                self.record_resolve(delivery_name, "2d_recipients_by_occupancy", recipients)
                recipients = [
                    r for r in recipients if self.recipients_override is None or r.get(CONF_PERSON) in self.recipients_override
                ]
                self.record_resolve(
                    delivery_name, "2d_recipient_names_by_occupancy_filtered", [r.get(CONF_PERSON) for r in recipients]
                )
                _LOGGER.debug("SUPERNOTIFY %s Using recipients: %s", delivery_name, recipients)

        return self.context.snoozer.filter_recipients(
            recipients, self.priority, delivery_name, delivery_method, self.selected_delivery_names, self.context.deliveries
        )

    def generate_envelopes(
        self, delivery_name: str, method: DeliveryMethod, recipients: list[dict[str, Any]]
    ) -> list[Envelope]:
        # now the list of recipients determined, resolve this to target addresses or entities

        delivery_config: dict[str, Any] = method.delivery_config(delivery_name)
        default_data: dict[str, Any] = delivery_config.get(CONF_DATA, {})
        default_targets: list[str] = []
        custom_envelopes: list[Envelope] = []

        for recipient in recipients:
            recipient_targets: list[str] = []
            enabled: bool = True
            custom_data: dict[str, Any] = {}
            # reuse standard recipient attributes like email or phone
            safe_extend(recipient_targets, method.recipient_target(recipient))
            # use entities or targets set at a method level for recipient
            if CONF_DELIVERY in recipient and delivery_config[CONF_NAME] in recipient.get(CONF_DELIVERY, {}):
                recp_meth_cust = recipient.get(CONF_DELIVERY, {}).get(delivery_config[CONF_NAME], {})
                safe_extend(recipient_targets, recp_meth_cust.get(CONF_TARGET, []))
                custom_data = recp_meth_cust.get(CONF_DATA)
                enabled = recp_meth_cust.get(CONF_ENABLED, True)
            elif ATTR_TARGET in recipient:
                # non person recipient
                safe_extend(default_targets, recipient.get(ATTR_TARGET))
            if enabled:
                if custom_data:
                    envelope_data = {}
                    envelope_data.update(default_data)
                    envelope_data.update(self.data)
                    envelope_data.update(custom_data)
                    custom_envelopes.append(Envelope(delivery_name, self, recipient_targets, envelope_data))
                else:
                    default_targets.extend(recipient_targets)

        envelope_data = {}
        envelope_data.update(default_data)
        envelope_data.update(self.data)

        bundled_envelopes = [*custom_envelopes, Envelope(delivery_name, self, default_targets, envelope_data)]
        filtered_envelopes = []
        for envelope in bundled_envelopes:
            pre_filter_count = len(envelope.targets)
            _LOGGER.debug("SUPERNOTIFY Prefiltered targets: %s", envelope.targets)
            targets = [t for t in envelope.targets if method.select_target(t)]
            if len(targets) < pre_filter_count:
                _LOGGER.warning(
                    "SUPERNOTIFY %s target list filtered out %s",
                    method.method,
                    [t for t in envelope.targets if not method.select_target(t)],
                )
            if not targets:
                _LOGGER.debug("SUPERNOTIFY %s No targets resolved out of %s", method.method, pre_filter_count)
            else:
                envelope.targets = targets
                filtered_envelopes.append(envelope)

        if not filtered_envelopes:
            # not all delivery methods require explicit targets, or can default them internally
            filtered_envelopes = [Envelope(delivery_name, self, data=envelope_data)]
        return filtered_envelopes

    async def grab_image(self, delivery_name: str) -> Path | None:
        snapshot_url = self.media.get(ATTR_MEDIA_SNAPSHOT_URL)
        camera_entity_id = self.media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
        delivery_config = self.delivery_data(delivery_name)
        jpeg_opts = self.media.get(ATTR_JPEG_OPTS, delivery_config.get(CONF_OPTIONS, {}).get(ATTR_JPEG_OPTS))

        if not snapshot_url and not camera_entity_id:
            return None

        image_path: Path | None = None
        if self.snapshot_image_path is not None:
            return self.snapshot_image_path
        if snapshot_url and self.context.media_path and self.context.hass:
            image_path = await snapshot_from_url(
                self.context.hass, snapshot_url, self.id, self.context.media_path, self.context.hass_internal_url, jpeg_opts
            )
        elif camera_entity_id and camera_entity_id.startswith("image.") and self.context.hass and self.context.media_path:
            image_path = await snap_image(self.context, camera_entity_id, self.context.media_path, self.id, jpeg_opts)
        elif camera_entity_id:
            if not self.context.hass or not self.context.media_path:
                _LOGGER.warning("SUPERNOTIFY No homeassistant ref or media path for camera %s", camera_entity_id)
                return None
            active_camera_entity_id = select_avail_camera(self.context.hass, self.context.cameras, camera_entity_id)
            if active_camera_entity_id:
                camera_config = self.context.cameras.get(active_camera_entity_id, {})
                camera_delay = self.media.get(ATTR_MEDIA_CAMERA_DELAY, camera_config.get(CONF_PTZ_DELAY))
                camera_ptz_preset_default = camera_config.get(CONF_PTZ_PRESET_DEFAULT)
                camera_ptz_method = camera_config.get(CONF_PTZ_METHOD)
                camera_ptz_preset = self.media.get(ATTR_MEDIA_CAMERA_PTZ_PRESET)
                _LOGGER.debug(
                    "SUPERNOTIFY snapping camera %s, ptz %s->%s, delay %s secs",
                    active_camera_entity_id,
                    camera_ptz_preset,
                    camera_ptz_preset_default,
                    camera_delay,
                )
                if camera_ptz_preset:
                    await move_camera_to_ptz_preset(
                        self.context.hass, active_camera_entity_id, camera_ptz_preset, method=camera_ptz_method
                    )
                if camera_delay:
                    _LOGGER.debug("SUPERNOTIFY Waiting %s secs before snapping", camera_delay)
                    await asyncio.sleep(camera_delay)
                image_path = await snap_camera(
                    self.context.hass,
                    active_camera_entity_id,
                    media_path=self.context.media_path,
                    max_camera_wait=15,
                    jpeg_opts=jpeg_opts,
                )
                if camera_ptz_preset and camera_ptz_preset_default:
                    await move_camera_to_ptz_preset(
                        self.context.hass, active_camera_entity_id, camera_ptz_preset_default, method=camera_ptz_method
                    )

        if image_path is None:
            _LOGGER.warning("SUPERNOTIFY No media available to attach (%s,%s)", snapshot_url, camera_entity_id)
            return None
        self.snapshot_image_path = image_path
        return image_path
