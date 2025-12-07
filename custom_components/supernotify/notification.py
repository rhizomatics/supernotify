import datetime as dt
import logging
import string
import uuid
from traceback import format_exception
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.notify.const import ATTR_DATA
from homeassistant.const import CONF_ENABLED
from jinja2 import TemplateError
from voluptuous import humanize

from custom_components.supernotify import (
    ACTION_DATA_SCHEMA,
    ATTR_ACTION_GROUPS,
    ATTR_ACTIONS,
    ATTR_DEBUG,
    ATTR_DELIVERY,
    ATTR_DELIVERY_SELECTION,
    ATTR_MEDIA,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_MESSAGE_HTML,
    ATTR_PERSON_ID,
    ATTR_PRIORITY,
    ATTR_RECIPIENTS,
    ATTR_SCENARIOS_APPLY,
    ATTR_SCENARIOS_CONSTRAIN,
    ATTR_SCENARIOS_REQUIRE,
    CONF_DATA,
    DELIVERY_SELECTION_EXPLICIT,
    DELIVERY_SELECTION_FIXED,
    DELIVERY_SELECTION_IMPLICIT,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_UNIQUE_TARGETS,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    SCENARIO_NULL,
    SELECTION_BY_SCENARIO,
    STRICT_ACTION_DATA_SCHEMA,
    TARGET_USE_FIXED,
    TARGET_USE_MERGE_ALWAYS,
    TARGET_USE_MERGE_ON_DELIVERY_TARGETS,
    TARGET_USE_ON_NO_ACTION_TARGETS,
    TARGET_USE_ON_NO_DELIVERY_TARGETS,
    SelectionRank,
)

from .archive import ArchivableObject
from .common import ensure_dict, ensure_list
from .context import Context
from .delivery import Delivery, DeliveryRegistry
from .envelope import Envelope
from .model import ConditionVariables, MessageOnlyPolicy, SuppressionReason, Target, TargetRequired
from .scenario import Scenario

if TYPE_CHECKING:
    from pathlib import Path

    from custom_components.supernotify.people import PeopleRegistry
    from custom_components.supernotify.transport import (
        Transport,
    )

    from .people import Recipient

_LOGGER = logging.getLogger(__name__)


HASH_PREP_TRANSLATION_TABLE = table = str.maketrans("", "", string.punctuation + string.digits)


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
        self.people_registry: PeopleRegistry = context.people_registry
        self.delivery_registry: DeliveryRegistry = context.delivery_registry
        action_data = action_data or {}
        self.target: Target | None = Target(target) if target else None
        self.selected: Target = Target()
        self._title: str | None = title
        self.id = str(uuid.uuid1())
        self.snapshot_image_path: Path | None = None
        self.delivered: int = 0
        self.errored: int = 0
        self.skipped: int = 0
        self.missed: int = 0
        self.delivered_envelopes: list[Envelope] = []
        self.undelivered_envelopes: list[Envelope] = []
        self.delivery_error: list[str] | None = None

        self.validate_action_data(action_data)
        # for compatibility with other notify calls, pass thru surplus data to underlying delivery transports
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
        self.actions: list[dict[str, Any]] = action_data.get(ATTR_ACTIONS) or []
        self.delivery_results: dict[str, Any] = {}
        self.delivery_errors: dict[str, Any] = {}

        self.selected_delivery_names: list[str] = []
        self.enabled_scenarios: dict[str, Scenario] = {}
        self.selected_scenario_names: list[str] = []
        self.suppressed: SuppressionReason | None = None
        self.condition_variables: ConditionVariables

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

        self.occupancy: dict[str, list[Recipient]] = self.people_registry.determine_occupancy()
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
            self.suppress(SuppressionReason.NO_SCENARIO)
        else:
            for s in enabled_scenario_names:
                scenario_obj = self.context.scenario_registry.scenarios.get(s)
                if scenario_obj is not None:
                    self.enabled_scenarios[s] = scenario_obj

            self.selected_delivery_names = self.select_deliveries()
            if self.context.snoozer.is_global_snooze(self.priority):
                self.suppress(SuppressionReason.SNOOZED)
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
                scenario_enable_deliveries.extend(self.context.scenario_registry.delivery_by_scenario.get(scenario_name, ()))
            if self.delivery_selection == DELIVERY_SELECTION_IMPLICIT:
                default_enable_deliveries = [d.name for d in self.context.delivery_registry.implicit_deliveries]

        self.debug_trace.record_delivery_selection("scenario_enable_deliveries", scenario_enable_deliveries)
        self.debug_trace.record_delivery_selection("default_enable_deliveries", default_enable_deliveries)
        self.debug_trace.record_delivery_selection("scenario_disable_deliveries", scenario_disable_deliveries)

        override_enable_deliveries = []
        override_disable_deliveries = []

        for delivery, delivery_override in self.delivery_overrides.items():
            if (
                delivery_override is None or delivery_override.get(CONF_ENABLED, True)
            ) and delivery in self.context.delivery_registry.deliveries:
                override_enable_deliveries.append(delivery)
            elif delivery_override is not None and not delivery_override.get(CONF_ENABLED, True):
                override_disable_deliveries.append(delivery)

        if self.delivery_selection != DELIVERY_SELECTION_FIXED:
            scenario_disable_deliveries = [
                d.name
                for d in self.context.delivery_registry.deliveries.values()
                if d.selection == [SELECTION_BY_SCENARIO]
                and d.name not in scenario_enable_deliveries
                and (d.name not in override_enable_deliveries or self.delivery_selection != DELIVERY_SELECTION_EXPLICIT)
            ]
        all_enabled = list(set(scenario_enable_deliveries + default_enable_deliveries + override_enable_deliveries))
        all_disabled = scenario_disable_deliveries + override_disable_deliveries
        self.debug_trace.record_delivery_selection("override_disable_deliveries", override_disable_deliveries)
        self.debug_trace.record_delivery_selection("override_enable_deliveries", override_enable_deliveries)

        unsorted_objs: list[Delivery] = [self.delivery_registry.deliveries[d] for d in all_enabled if d not in all_disabled]
        first: list[str] = [d.name for d in unsorted_objs if d.selection_rank == SelectionRank.FIRST]
        anywhere: list[str] = [d.name for d in unsorted_objs if d.selection_rank == SelectionRank.ANY]
        last: list[str] = [d.name for d in unsorted_objs if d.selection_rank == SelectionRank.LAST]
        selected = first + anywhere + last
        self.debug_trace.record_delivery_selection("ranked", selected)
        return selected

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
        template_scenario_names = self.context.scenario_registry.content_scenario_templates.get(template_field, {}).get(
            delivery_name, []
        )
        if not template_scenario_names:
            return original
        context_vars = self.condition_variables.as_dict() if self.condition_variables else {}
        rendered = original if original is not None else ""
        for scen_obj in [obj for name, obj in self.enabled_scenarios.items() if name in template_scenario_names]:
            context_vars[matching_ctx] = rendered
            try:
                template_format = scen_obj.delivery.get(delivery_name, {}).get(CONF_DATA, {}).get(template_field)
                if template_format is not None:
                    template = self.context.hass_api.template(template_format)
                    rendered = template.async_render(variables=context_vars)
            except TemplateError as e:
                _LOGGER.warning("SUPERNOTIFY Rendering template %s for %s failed: %s", template_field, delivery_name, e)
        return rendered

    def message(self, delivery_name: str) -> str | None:
        # message and title reverse the usual defaulting, delivery config overrides runtime call
        delivery_config: Delivery | None = self.context.delivery_registry.deliveries.get(delivery_name)
        msg: str | None = None
        if delivery_config is None:
            msg = self._message
        else:
            msg = delivery_config.message if delivery_config.message is not None else self._message
            message_usage: str = str(delivery_config.option_str(OPTION_MESSAGE_USAGE))
            if message_usage.upper() == MessageOnlyPolicy.USE_TITLE:
                title = self.title(delivery_name, ignore_usage=True)
                if title:
                    msg = title
            elif message_usage.upper() == MessageOnlyPolicy.COMBINE_TITLE:
                title = self.title(delivery_name, ignore_usage=True)
                if title:
                    msg = f"{title} {msg}"
            if (
                delivery_config.option_bool(OPTION_SIMPLIFY_TEXT) is True
                or delivery_config.option_bool(OPTION_STRIP_URLS) is True
            ):
                msg = delivery_config.transport.simplify(msg, strip_urls=delivery_config.option_bool(OPTION_STRIP_URLS))

        msg = self._render_scenario_templates(msg, "message_template", "notification_message", delivery_name)
        if msg is None:  # keep mypy happy
            return None
        return str(msg)

    def title(self, delivery_name: str, ignore_usage: bool = False) -> str | None:
        # message and title reverse the usual defaulting, delivery config overrides runtime call
        delivery_config: Delivery | None = self.context.delivery_registry.deliveries.get(delivery_name)
        title: str | None = None
        if delivery_config is None:
            title = self._title
        else:
            message_usage = delivery_config.option_str(OPTION_MESSAGE_USAGE)
            if not ignore_usage and message_usage.upper() in (MessageOnlyPolicy.USE_TITLE, MessageOnlyPolicy.COMBINE_TITLE):
                title = None
            else:
                title = delivery_config.title if delivery_config.title is not None else self._title
                if (
                    delivery_config.option_bool(OPTION_SIMPLIFY_TEXT) is True
                    or delivery_config.option_bool(OPTION_STRIP_URLS) is True
                ):
                    title = delivery_config.transport.simplify(title, strip_urls=delivery_config.option_bool(OPTION_STRIP_URLS))
        title = self._render_scenario_templates(title, "title_template", "notification_title", delivery_name)
        if title is None:
            return None
        return str(title)

    def suppress(self, reason: SuppressionReason) -> None:
        self.suppressed = reason
        _LOGGER.info(f"SUPERNOTIFY Suppressing notification, reason:{reason}, id:{self.id}")

    async def deliver(self) -> bool:
        if self.suppressed is not None:
            _LOGGER.info("SUPERNOTIFY Suppressing globally silenced/snoozed notification (%s)", self.id)
            self.skipped += 1
            return False

        _LOGGER.debug(
            "Message: %s, notification: %s, deliveries: %s",
            self._message,
            self.id,
            self.selected_delivery_names,
        )

        for delivery_name in self.selected_delivery_names:
            delivery = self.context.delivery_registry.deliveries.get(delivery_name)
            if delivery:
                await self.call_transport(delivery)
            else:
                _LOGGER.error(f"SUPERNOTIFY Unexpected missing delivery {delivery_name}")

        if self.delivered == 0 and self.errored == 0:
            for delivery in self.context.delivery_registry.fallback_by_default_deliveries:
                if delivery.name not in self.selected_delivery_names:
                    await self.call_transport(delivery)

        if self.delivered == 0 and self.errored > 0:
            for delivery in self.context.delivery_registry.fallback_on_error_deliveries:
                if delivery.name not in self.selected_delivery_names:
                    await self.call_transport(delivery)

        return self.delivered > 0

    async def call_transport(self, delivery: Delivery) -> None:
        try:
            transport: Transport = delivery.transport
            if not transport.override_enabled:
                self.skipped += 1
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on transport disabled", delivery)
                return

            delivery_priorities = delivery.priority
            if self.priority and delivery_priorities and self.priority not in delivery_priorities:
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on priority (%s)", delivery, self.priority)
                self.skipped += 1
                return
            if not delivery.evaluate_conditions(self.condition_variables):
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on conditions", delivery)
                self.skipped += 1
                return

            recipients: list[Target] = self.generate_recipients(delivery)
            envelopes = self.generate_envelopes(delivery, recipients)
            for envelope in envelopes:
                try:
                    if not await transport.deliver(envelope):
                        self.missed += 1
                    self.delivered += envelope.delivered
                    self.errored += envelope.errored
                    if envelope.delivered:
                        self.delivered_envelopes.append(envelope)
                    else:
                        self.undelivered_envelopes.append(envelope)
                except Exception as e2:
                    _LOGGER.exception("SUPERNOTIFY Failed to deliver %s: %s", envelope.delivery_name, e2)
                    self.errored += 1
                    transport.record_error(str(e2), method="deliver")
                    envelope.delivery_error = format_exception(e2)
                    self.undelivered_envelopes.append(envelope)

        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Failed to notify using %s", delivery.name)
            _LOGGER.debug("SUPERNOTIFY %s delivery failure", delivery, exc_info=True)
            self.delivery_errors[delivery.name] = format_exception(e)

    def hash(self) -> int:
        """Alpha hash to reduce noise from messages with timestamps or incrementing counts"""

        def alphaize(v: str | None) -> str | None:
            return v.translate(HASH_PREP_TRANSLATION_TABLE) if v else v

        return hash((alphaize(self._message), alphaize(self._title)))

    def contents(self, minimal: bool = False) -> dict[str, Any]:
        """ArchiveableObject implementation"""
        object_refs = ("context", "people_registry", "delivery_registry")
        sanitized = {k: v for k, v in self.__dict__.items() if k not in object_refs and not k.startswith("_")}
        sanitized["delivered_envelopes"] = [e.contents(minimal=minimal) for e in self.delivered_envelopes]
        sanitized["undelivered_envelopes"] = [e.contents(minimal=minimal) for e in self.undelivered_envelopes]
        sanitized["enabled_scenarios"] = {k: v.contents(minimal=minimal) for k, v in self.enabled_scenarios.items()}
        if sanitized["target"]:
            sanitized["target"] = sanitized["target"].as_dict()
        if sanitized["selected"]:
            sanitized["selected"] = sanitized["selected"].as_dict()
        if sanitized["condition_variables"]:
            sanitized["condition_variables"] = sanitized["condition_variables"].as_dict()
        if sanitized["occupancy"]:
            sanitized["occupancy"] = {k: [v.as_dict() for v in vs] for k, vs in sanitized["occupancy"].items()}

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
            s: obj
            for s, obj in self.enabled_scenarios.items()
            if delivery_name in self.context.scenario_registry.delivery_by_scenario.get(s, [])
        }

    async def select_scenarios(self) -> list[str]:
        return [s.name for s in self.context.scenario_registry.scenarios.values() if s.evaluate(self.condition_variables)]

    def merge(self, attribute: str, delivery_name: str) -> dict[str, Any]:
        delivery: dict[str, Any] = self.delivery_overrides.get(delivery_name, {})
        base: dict[str, Any] = delivery.get(attribute, {})
        for scenario in self.enabled_scenarios.values():
            if scenario and hasattr(scenario, attribute):
                base.update(getattr(scenario, attribute))
        if hasattr(self, attribute):
            base.update(getattr(self, attribute))
        return base

    def generate_recipients(self, delivery: Delivery) -> list[Target]:

        if delivery.target_required == TargetRequired.NEVER:
            # don't waste time computing targets for deliveries that don't need them
            return [Target(None, target_data=delivery.data)]

        computed_target: Target

        if delivery.target_usage == TARGET_USE_FIXED:
            if delivery.target:
                computed_target = delivery.target.safe_copy()
                self.debug_trace.record_target(delivery.name, "1a_delivery_default_fixed", computed_target)
            else:
                computed_target = Target(None, target_data=delivery.data)
                self.debug_trace.record_target(delivery.name, "1b_delivery_default_fixed_empty", computed_target)

        elif not self.target:
            # Unless there are explicit targets, include everyone on the people registry
            computed_target = self.default_person_ids(delivery)
            self.debug_trace.record_target(delivery.name, "1c_no_action_target", computed_target)
        else:
            computed_target = self.target.safe_copy()
            self.debug_trace.record_target(delivery.name, "1d_action_target", computed_target)

        # 1st round of filtering for snooze and resolving people->direct targets
        computed_target = self.context.snoozer.filter_recipients(computed_target, self.priority, delivery)
        self.debug_trace.record_target(delivery.name, "2a_post_snooze", computed_target)
        # turn person_ids into emails and phone numbers
        computed_target += self.resolve_indirect_targets(computed_target, delivery)
        self.debug_trace.record_target(delivery.name, "2b_resolve_indirect", computed_target)
        # filter out target not required for this delivery
        computed_target = delivery.select_targets(computed_target)
        self.debug_trace.record_target(delivery.name, "2c_delivery_selection", computed_target)
        primary_count = len(computed_target)

        if delivery.target_usage == TARGET_USE_ON_NO_DELIVERY_TARGETS:
            if not computed_target.has_targets() and delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "3a_delivery_default_no_delivery_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_ON_NO_ACTION_TARGETS:
            if not self.target and delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "3b_delivery_default_no_action_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_MERGE_ON_DELIVERY_TARGETS:
            # merge in the delivery defaults if there's a target defined in action call
            if computed_target.has_targets() and delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "3c_delivery_merge_on_delivery_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_MERGE_ALWAYS:
            # merge in the delivery defaults even if there's not a target defined in action call
            if delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "3d_delivery_merge_always_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_FIXED:
            _LOGGER.debug("SUPERNOTIFY Fixed target on delivery %s", delivery.name)
        else:
            self.debug_trace.record_target(delivery.name, "3f_no_target_usage_match", computed_target)
            _LOGGER.debug("SUPERNOTIFY No useful target definition for delivery %s", delivery.name)

        if len(computed_target) > primary_count:
            _LOGGER.debug(
                "SUPERNOTIFY Delivery config added %s targets for %s", len(computed_target) - primary_count, delivery.name
            )

            # 2nd round of filtering for snooze and resolving people->direct targets after delivery target applied
            computed_target = self.context.snoozer.filter_recipients(computed_target, self.priority, delivery)
            self.debug_trace.record_target(delivery.name, "4a_post_snooze", computed_target)
            computed_target += self.resolve_indirect_targets(computed_target, delivery)
            self.debug_trace.record_target(delivery.name, "4b_resolved_indirect_targets", computed_target)
            computed_target = delivery.select_targets(computed_target)
            self.debug_trace.record_target(delivery.name, "4c_delivery_selection", computed_target)

        split_targets: list[Target] = computed_target.split_by_target_data()
        self.debug_trace.record_target(delivery.name, "5a_delivery_split_targets", split_targets)
        direct_targets: list[Target] = [t.direct() for t in split_targets]
        self.debug_trace.record_target(delivery.name, "5b_narrow_to_direct", direct_targets)
        if delivery.options.get(OPTION_UNIQUE_TARGETS, False):
            direct_targets = [t - self.selected for t in direct_targets]
            self.debug_trace.record_target(delivery.name, "5c_make_unique_across_deliveries", direct_targets)
        for direct_target in direct_targets:
            self.selected += direct_target
        self.debug_trace.record_target(delivery.name, "6_final_cut", direct_targets)
        return direct_targets

    def default_person_ids(self, delivery: Delivery) -> Target:
        # If target not specified on service call or delivery, then default to std list of recipients
        people: list[Recipient] = self.people_registry.filter_people_by_occupancy(delivery.occupancy)
        people = [p for p in people if self.recipients_override is None or p.entity_id in self.recipients_override]
        return Target({ATTR_PERSON_ID: [p.entity_id for p in people if p.entity_id]})

    def resolve_indirect_targets(self, target: Target, delivery: Delivery) -> Target:
        # enrich data selected in configuration for this delivery, from direct target definition or attrs like email or phone
        resolved: Target = Target()

        for person_id in target.person_ids:
            person = self.people_registry.people.get(person_id)
            if person and person.enabled:
                recipient_target = Target({ATTR_PERSON_ID: [person_id]})
                if person.target is not None and person.target.has_resolved_target():
                    recipient_target += person.target
                personal_delivery = person.delivery.get(delivery.name) if person.delivery else None
                if personal_delivery:
                    if personal_delivery.enabled and personal_delivery.target:
                        if personal_delivery.target.has_resolved_target():
                            recipient_target += personal_delivery.target
            else:
                _LOGGER.debug("SUPERNOTIFY Skipping recipient %s with enabled switched off", person_id)

            resolved += recipient_target
        return resolved

    def generate_envelopes(self, delivery: Delivery, targets: list[Target]) -> list[Envelope]:
        # now the list of recipients determined, resolve this to target addresses or entities

        default_data: dict[str, Any] = delivery.data

        envelopes = []
        for target in targets:
            if target.has_resolved_target() or delivery.target_required != TargetRequired.ALWAYS:
                envelope_data = {}
                envelope_data.update(default_data)
                envelope_data.update(self.data)
                if target.target_data:
                    envelope_data.update(target.target_data)
                envelopes.append(Envelope(delivery, self, target, envelope_data))

        return envelopes


class DebugTrace:
    def __init__(
        self,
        message: str | None,
        title: str | None,
        data: dict[str, Any] | None,
        target: dict[str, list[str]] | list[str] | str | None,
    ) -> None:
        self.message: str | None = message
        self.title: str | None = title
        self.data: dict[str, Any] | None = data
        self.target: dict[str, list[str]] | list[str] | str | None = target
        self.resolved: dict[str, dict[str, Any]] = {}
        self.delivery_selection: dict[str, list[str]] = {}
        self._last_stage: dict[str, str] = {}

    def contents(
        self,
    ) -> dict[str, Any]:
        return {
            "message": self.message,
            "title": self.title,
            "data": self.data,
            "target": self.target,
            "resolved": self.resolved,
            "delivery_selection": self.delivery_selection,
        }

    def record_target(self, delivery_name: str, stage: str, computed: Target | list[Target]) -> None:
        """Debug support for recording detailed target resolution in archived notification"""
        self.resolved.setdefault(delivery_name, {})
        self.resolved[delivery_name].setdefault(stage, {})
        if isinstance(computed, Target):
            combined = computed
        else:
            combined = Target()
            for target in ensure_list(computed):
                combined += target
        result: str | dict[str, Any] = combined.as_dict()
        if self._last_stage.get(delivery_name):
            last_target = self.resolved[delivery_name][self._last_stage[delivery_name]]
            if last_target is not None and last_target == result:
                result = "NO_CHANGE"

        self.resolved[delivery_name][stage] = result
        self._last_stage[delivery_name] = stage

    def record_delivery_selection(self, stage: str, delivery_selection: list[str]) -> None:
        """Debug support for recording detailed target resolution in archived notification"""
        self.delivery_selection[stage] = delivery_selection
