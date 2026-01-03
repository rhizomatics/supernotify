import datetime as dt
import logging
import uuid
from traceback import format_exception
from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant.components.notify.const import ATTR_DATA
from voluptuous import humanize

from . import (
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
    DELIVERY_SELECTION_EXPLICIT,
    DELIVERY_SELECTION_FIXED,
    DELIVERY_SELECTION_IMPLICIT,
    OPTION_UNIQUE_TARGETS,
    PRIORITY_MEDIUM,
    PRIORITY_VALUES,
    STRICT_ACTION_DATA_SCHEMA,
    TARGET_USE_FIXED,
    TARGET_USE_MERGE_ALWAYS,
    TARGET_USE_MERGE_ON_DELIVERY_TARGETS,
    TARGET_USE_ON_NO_ACTION_TARGETS,
    TARGET_USE_ON_NO_DELIVERY_TARGETS,
    SelectionRank,
)
from .archive import ArchivableObject
from .common import ensure_list, nullable_ensure_list, sanitize
from .context import Context
from .delivery import Delivery, DeliveryRegistry
from .envelope import Envelope
from .model import ConditionVariables, DebugTrace, DeliveryCustomization, SuppressionReason, Target, TargetRequired
from .people import Recipient

if TYPE_CHECKING:
    from .people import PeopleRegistry
    from .scenario import Scenario
    from .transport import (
        Transport,
    )

_LOGGER = logging.getLogger(__name__)

# Deliveries mapping keys for debug / archive
KEY_DELIVERED = "delivered"
KEY_SUPPRESSED = "suppressed"
KEY_FAILED = "failed"
KEY_SKIPPED = "skipped"

type t_delivery_name = str
type t_outcome = str


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
        self.message: str | None = message
        self.context: Context = context
        self.people_registry: PeopleRegistry = context.people_registry
        self.delivery_registry: DeliveryRegistry = context.delivery_registry
        action_data = action_data or {}
        self._target: Target | None = Target(target) if target else None
        self._already_selected: Target = Target()
        self._title: str | None = title
        self.id = str(uuid.uuid1())
        self.delivered: int = 0
        self.error_count: int = 0
        self.skipped: int = 0
        self.failed: int = 0
        self.suppressed: int = 0
        self.dupe: bool = False
        self.deliveries: dict[t_delivery_name, dict[t_outcome, list[str] | list[Envelope] | dict[str, Any]]] = {}
        self._skip_reasons: list[SuppressionReason] = []

        self.validate_action_data(action_data)
        # for compatibility with other notify calls, pass thru surplus data to underlying delivery transports
        self.extra_data: dict[str, Any] = {
            k: v for k, v in action_data.items() if k not in STRICT_ACTION_DATA_SCHEMA(action_data)
        }
        action_data = {k: v for k, v in action_data.items() if k not in self.extra_data}

        self.priority: str = action_data.get(ATTR_PRIORITY, PRIORITY_MEDIUM)
        self.message_html: str | None = action_data.get(ATTR_MESSAGE_HTML)
        self.required_scenario_names: list[str] = ensure_list(action_data.get(ATTR_SCENARIOS_REQUIRE))
        self.applied_scenario_names: list[str] = ensure_list(action_data.get(ATTR_SCENARIOS_APPLY))
        self.constrain_scenario_names: list[str] = ensure_list(action_data.get(ATTR_SCENARIOS_CONSTRAIN))
        self.delivery_selection: str | None = action_data.get(ATTR_DELIVERY_SELECTION)
        self.delivery_overrides: dict[str, DeliveryCustomization] = {}

        delivery_data = action_data.get(ATTR_DELIVERY)
        if isinstance(delivery_data, list):
            # a bare list of deliveries implies intent to restrict
            _LOGGER.debug("SUPERNOTIFY defaulting delivery selection as explicit for list %s", delivery_data)
            if self.delivery_selection is None:
                self.delivery_selection = DELIVERY_SELECTION_EXPLICIT
            self.delivery_overrides = {k: DeliveryCustomization({}) for k in action_data.get(ATTR_DELIVERY, [])}
        elif isinstance(delivery_data, str) and delivery_data:
            # a bare list of deliveries implies intent to restrict
            _LOGGER.debug("SUPERNOTIFY defaulting delivery selection as explicit for single %s", delivery_data)
            if self.delivery_selection is None:
                self.delivery_selection = DELIVERY_SELECTION_EXPLICIT
            self.delivery_overrides = {delivery_data: DeliveryCustomization({})}
        elif isinstance(delivery_data, dict):
            # whereas a dict may be used to tune or restrict
            if self.delivery_selection is None:
                self.delivery_selection = DELIVERY_SELECTION_IMPLICIT
            _LOGGER.debug("SUPERNOTIFY defaulting delivery selection as implicit for mapping %s", delivery_data)
            self.delivery_overrides = {k: DeliveryCustomization(v) for k, v in action_data.get(ATTR_DELIVERY, {}).items()}
        elif delivery_data:
            _LOGGER.warning("SUPERNOTIFY Unable to interpret delivery data %s", delivery_data)
            if self.delivery_selection is None:
                self.delivery_selection = DELIVERY_SELECTION_IMPLICIT
        else:
            if self.delivery_selection is None:
                self.delivery_selection = DELIVERY_SELECTION_IMPLICIT

        self.action_groups: list[str] | None = nullable_ensure_list(action_data.get(ATTR_ACTION_GROUPS))
        self.recipients_override: list[str] | None = nullable_ensure_list(action_data.get(ATTR_RECIPIENTS))
        self.extra_data.update(action_data.get(ATTR_DATA, {}))
        self.media: dict[str, Any] = action_data.get(ATTR_MEDIA) or {}
        self.debug: bool = action_data.get(ATTR_DEBUG, False)
        self.actions: list[dict[str, Any]] = ensure_list(action_data.get(ATTR_ACTIONS))

        self.selected_deliveries: dict[str, dict[str, Any]] = {}
        self.enabled_scenarios: dict[str, Scenario] = {}
        self.selected_scenario_names: list[str] = []
        self._suppression_reason: SuppressionReason | None = None
        self._delivery_error: list[str] | None = None
        self.condition_variables: ConditionVariables

    async def initialize(self) -> None:
        """Async post-construction initialization"""
        self.occupancy: dict[str, list[Recipient]] = self.people_registry.determine_occupancy()
        self.condition_variables = ConditionVariables(
            self.applied_scenario_names,
            self.required_scenario_names,
            self.constrain_scenario_names,
            self.priority,
            self.occupancy,
            self.message,
            self._title,
        )  # requires occupancy first

        enabled_scenario_names: list[str] = list(self.applied_scenario_names) or []
        self.selected_scenario_names = await self.select_scenarios()
        enabled_scenario_names.extend(self.selected_scenario_names)
        if self.constrain_scenario_names:
            enabled_scenario_names = [
                s for s in enabled_scenario_names if (s in self.constrain_scenario_names or s in self.applied_scenario_names)
            ]
        if self.required_scenario_names and not any(s in enabled_scenario_names for s in self.required_scenario_names):
            _LOGGER.info("SUPERNOTIFY suppressing notification, no required scenarios enabled")
            self.selected_deliveries = {}
            self.suppress(SuppressionReason.NO_SCENARIO)
        else:
            for s in enabled_scenario_names:
                scenario_obj = self.context.scenario_registry.scenarios.get(s)
                if scenario_obj is not None:
                    self.enabled_scenarios[s] = scenario_obj

            self.selected_deliveries = self.select_deliveries()
            if self.context.snoozer.is_global_snooze(self.priority):
                self.suppress(SuppressionReason.SNOOZED)
            self.apply_enabled_scenarios()

        if not self.media:
            self.media = self.media_requirements(self.extra_data)

    def media_requirements(self, data: dict[str, Any]) -> dict[str, Any]:
        """If no media defined, look for iOS / Android actions that have media defined

        Example is the Frigate blueprint, which generates `image`, `video` etc
        in the `data` section, that can also be used for email attachments
        """
        media_dict = {}
        if not data:
            return {}
        if data.get("image"):
            media_dict[ATTR_MEDIA_SNAPSHOT_URL] = data.get("image")
        if data.get("video"):
            media_dict[ATTR_MEDIA_CLIP_URL] = data.get("video")
        if data.get("attachment", {}).get("url"):
            url = data["attachment"]["url"]
            if url and url.endswith(".mp4") and not media_dict.get(ATTR_MEDIA_CLIP_URL):
                media_dict[ATTR_MEDIA_CLIP_URL] = url
            elif (
                url
                and (url.endswith(".jpg") or url.endswith(".jpeg") or url.endswith(".png"))
                and not media_dict.get(ATTR_MEDIA_SNAPSHOT_URL)
            ):
                media_dict[ATTR_MEDIA_SNAPSHOT_URL] = url
        return media_dict

    def validate_action_data(self, action_data: dict[str, Any]) -> None:
        if action_data.get(ATTR_PRIORITY) and action_data.get(ATTR_PRIORITY) not in PRIORITY_VALUES:
            _LOGGER.info("SUPERNOTIFY custom priority %s", action_data.get(ATTR_PRIORITY))
        try:
            humanize.validate_with_humanized_errors(action_data, ACTION_DATA_SCHEMA)
        except vol.Invalid as e:
            _LOGGER.warning("SUPERNOTIFY invalid service data %s: %s", action_data, e)
            raise

    def apply_enabled_scenarios(self) -> None:
        """Set media and action_groups from scenario if defined, first come first applied"""
        action_groups: list[str] = []
        for scenario in self.enabled_scenarios.values():
            if scenario.media:
                if self.media:
                    self.media.update(scenario.media)
                else:
                    self.media = scenario.media
            if scenario.action_groups:
                action_groups.extend(ag for ag in scenario.action_groups if ag not in action_groups)
        # self.action_groups only accessed from inside Envelope
        if self.action_groups:
            self.action_groups.extend(action_groups)
        else:
            self.action_groups = action_groups

    def select_deliveries(self) -> dict[str, dict[str, Any]]:
        scenario_enable_deliveries: list[str] = []
        scenario_disable_deliveries: list[str] = []
        default_enable_deliveries: list[str] = []
        recipients_enable_deliveries: list[str] = []

        if self.delivery_selection != DELIVERY_SELECTION_FIXED:
            for scenario in self.enabled_scenarios.values():
                scenario_enable_deliveries.extend(scenario.enabling_deliveries())
            for scenario in self.enabled_scenarios.values():
                scenario_disable_deliveries.extend(scenario.disabling_deliveries())

            scenario_enable_deliveries = list(set(scenario_enable_deliveries))
            scenario_disable_deliveries = list(set(scenario_disable_deliveries))

            for recipient in self.all_recipients():
                recipients_enable_deliveries.extend(recipient.enabling_delivery_names())
            if self.delivery_selection == DELIVERY_SELECTION_IMPLICIT:
                # all deliveries with SELECTION_DEFAULT in CONF_SELECTION
                default_enable_deliveries = [d.name for d in self.context.delivery_registry.implicit_deliveries]

        self.debug_trace.record_delivery_selection("scenario_enable_deliveries", scenario_enable_deliveries)
        self.debug_trace.record_delivery_selection("scenario_disable_deliveries", scenario_disable_deliveries)
        self.debug_trace.record_delivery_selection("default_enable_deliveries", default_enable_deliveries)
        self.debug_trace.record_delivery_selection("recipient_enable_deliveries", recipients_enable_deliveries)

        override_enable_deliveries: list[str] = []
        override_disable_deliveries: list[str] = []

        # apply the deliveries defined in the notification action call
        for delivery, delivery_override in self.delivery_overrides.items():
            if (
                (delivery_override is None or delivery_override.enabled is True)
                and delivery in self.context.delivery_registry.enabled_deliveries
            ) or (
                (delivery_override is not None and delivery_override.enabled is True)
                and delivery in self.context.delivery_registry.disabled_deliveries
            ):
                override_enable_deliveries.append(delivery)
            elif delivery_override is not None and delivery_override.enabled is False:
                override_disable_deliveries.append(delivery)

        # if self.delivery_selection != DELIVERY_SELECTION_FIXED:
        #    scenario_disable_deliveries = [
        #        d.name
        #        for d in self.context.delivery_registry.deliveries.values()
        #        if d.selection == [SELECTION_BY_SCENARIO]
        #        and d.name not in scenario_enable_deliveries
        #        and (d.name not in override_enable_deliveries or self.delivery_selection != DELIVERY_SELECTION_EXPLICIT)
        #    ]
        all_global_enabled: list[str] = list(
            set(scenario_enable_deliveries + default_enable_deliveries + override_enable_deliveries)
        )
        all_enabled: list[str] = all_global_enabled + recipients_enable_deliveries
        all_disabled: list[str] = scenario_disable_deliveries + override_disable_deliveries
        override_enabled: list[str] = list(set(scenario_enable_deliveries + override_enable_deliveries))
        self.debug_trace.record_delivery_selection("override_disable_deliveries", override_disable_deliveries)
        self.debug_trace.record_delivery_selection("override_enable_deliveries", override_enable_deliveries)

        unsorted_maybe_objs: list[Delivery | None] = [
            self.delivery_registry.deliveries.get(d) for d in all_enabled if d not in all_disabled
        ]
        unsorted_objs: list[Delivery] = [
            d for d in unsorted_maybe_objs if d is not None and (d.enabled or d.name in override_enabled)
        ]
        first: list[str] = [d.name for d in unsorted_objs if d.selection_rank == SelectionRank.FIRST]
        anywhere: list[str] = [d.name for d in unsorted_objs if d.selection_rank == SelectionRank.ANY]
        last: list[str] = [d.name for d in unsorted_objs if d.selection_rank == SelectionRank.LAST]
        selected = first + anywhere + last
        self.debug_trace.record_delivery_selection("ranked", selected)

        # TODO: clean up this ugly logic, reorganize delivery around people
        results: dict[str, dict[str, Any]] = {d: {} for d in selected}
        personal_deliveries = [d for d in selected if d not in all_global_enabled and d in recipients_enable_deliveries]
        for personal_delivery in personal_deliveries:
            results[personal_delivery].setdefault("recipients", [])
            for recipient in self.all_recipients():
                if personal_delivery in recipient.enabling_delivery_names():
                    results[personal_delivery]["recipients"].append(recipient.entity_id)
        return results

    def suppress(self, reason: SuppressionReason) -> None:
        self._suppression_reason = reason
        if reason not in self._skip_reasons:
            self._skip_reasons.append(reason)
        _LOGGER.info(f"SUPERNOTIFY Suppressing notification, reason:{reason}, id:{self.id}")

    async def deliver(self) -> bool:
        _LOGGER.debug(
            "Message: %s, notification: %s, deliveries: %s",
            self.message,
            self.id,
            self.selected_deliveries,
        )

        for delivery_name, details in self.selected_deliveries.items():
            self.deliveries[delivery_name] = {}
            delivery = self.context.delivery_registry.deliveries.get(delivery_name)
            if self._suppression_reason is not None:
                _LOGGER.info("SUPERNOTIFY Suppressing globally silenced/snoozed notification (%s)", self.id)
                self.record_result(delivery, suppression_reason=SuppressionReason.SNOOZED)
            elif delivery:
                await self.call_transport(delivery, recipients=details.get("recipients"))
            else:
                _LOGGER.error(f"SUPERNOTIFY Unexpected missing delivery {delivery_name}")

        if self.delivered == 0 and not self._suppression_reason:
            if self.failed == 0 and not self.dupe:
                for delivery in self.context.delivery_registry.fallback_by_default_deliveries:
                    if delivery.name not in self.selected_deliveries:
                        await self.call_transport(delivery)

            if self.failed > 0:
                for delivery in self.context.delivery_registry.fallback_on_error_deliveries:
                    if delivery.name not in self.selected_deliveries:
                        await self.call_transport(delivery)

        return self.delivered > 0

    async def call_transport(self, delivery: Delivery, recipients: list[str] | None = None) -> None:
        try:
            transport: Transport = delivery.transport
            if not transport.enabled:
                self.record_result(delivery, suppression_reason=SuppressionReason.TRANSPORT_DISABLED)
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on transport disabled", delivery)
                return

            delivery_priorities: list[str] = delivery.priority
            if self.priority and delivery_priorities and self.priority not in delivery_priorities:
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on priority (%s)", delivery, self.priority)
                self.record_result(delivery, suppression_reason=SuppressionReason.PRIORITY)
                return
            if not delivery.evaluate_conditions(self.condition_variables):
                _LOGGER.debug("SUPERNOTIFY Skipping delivery %s based on conditions", delivery)
                self.record_result(delivery, suppression_reason=SuppressionReason.DELIVERY_CONDITION)
                return

            targets: list[Target] = self.generate_targets(delivery, recipients=recipients)
            envelopes: list[Envelope] = self.generate_envelopes(delivery, targets)
            if not envelopes:
                if delivery.target_required == TargetRequired.ALWAYS and (
                    not targets or not any(t.has_resolved_target() for t in targets)
                ):
                    reason: SuppressionReason = SuppressionReason.NO_TARGET
                else:
                    reason = SuppressionReason.UNKNOWN
                self.record_result(delivery, targets=targets, suppression_reason=reason)

            for envelope in envelopes:
                if self.context.dupe_checker.check(envelope):
                    _LOGGER.debug("SUPERNOTIFY Suppressing dupe envelope, %s", self.message)
                    self.record_result(delivery, envelope, suppression_reason=SuppressionReason.DUPE)
                    continue
                try:
                    if not await transport.deliver(envelope, debug_trace=self.debug_trace):
                        _LOGGER.debug("SUPERNOTIFY No delivery for %s", delivery.name)
                    self.record_result(delivery, envelope)
                except Exception as e2:
                    _LOGGER.exception("SUPERNOTIFY Failed to deliver %s: %s", delivery.name, e2)
                    envelope.error_count = envelope.error_count + 1
                    transport.record_error(str(e2), method="deliver")
                    envelope.delivery_error = format_exception(e2)
                    self.record_result(delivery, envelope)

        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Failed to notify using %s", delivery.name)
            _LOGGER.debug("SUPERNOTIFY %s delivery failure", delivery, exc_info=True)
            self.deliveries.setdefault(delivery.name, {})
            self.deliveries[delivery.name].setdefault("errors", [])
            errors: list[str] = cast("list[str]", self.deliveries[delivery.name]["errors"])
            errors.append("\n".join(format_exception(e)))

    def record_result(
        self,
        delivery: Delivery | None,
        envelope: Envelope | None = None,
        targets: list[Target] | None = None,
        suppression_reason: SuppressionReason | None = None,
    ) -> None:
        """Debugging (and unit test) support for notifications that failed or were skipped"""
        if delivery:
            if envelope:
                self.delivered += envelope.delivered
                self.error_count += envelope.error_count
                self.deliveries.setdefault(delivery.name, {})
                if envelope.delivered:
                    self.deliveries[delivery.name].setdefault(KEY_DELIVERED, [])
                    self.deliveries[delivery.name][KEY_DELIVERED].append(envelope)  # type: ignore
                else:
                    if suppression_reason:
                        envelope.skip_reason = suppression_reason
                        if suppression_reason not in self._skip_reasons:
                            self._skip_reasons.append(suppression_reason)
                        if suppression_reason == SuppressionReason.DUPE:
                            self.dupe = True
                    if envelope.error_count:
                        self.deliveries[delivery.name].setdefault(KEY_FAILED, [])
                        self.deliveries[delivery.name][KEY_FAILED].append(envelope)  # type: ignore
                        self.failed += 1
                    else:
                        self.deliveries[delivery.name].setdefault(KEY_SUPPRESSED, [])
                        self.deliveries[delivery.name][KEY_SUPPRESSED].append(envelope)  # type: ignore
                        self.suppressed += 1

        if not envelope:
            delivery_name: str = delivery.name if delivery else "!UNKNOWN!"
            skip_summary: dict[str, Any] = {
                "target_required": delivery.target_required if delivery else "!UNKNOWN!",
                "suppression_reason": str(suppression_reason),
            }
            self.deliveries.setdefault(delivery_name, {})
            if targets:
                skip_summary["targets"] = targets
            self.deliveries[delivery_name][KEY_SKIPPED] = skip_summary
            self.skipped += 1

    def contents(self, minimal: bool = False, **_kwargs: Any) -> dict[str, Any]:
        """ArchiveableObject implementation"""
        object_refs = ["context", "people_registry", "delivery_registry"]
        keys_only = ["enabled_scenarios"]
        debug_only = ["debug_trace"]
        exposed_if_populated = ["_delivery_error", "message_html", "extra_data", "actions", "_suppression_reason"]
        # fine tune dict order to ease the eye-burden when reviewing archived notifications
        preferred_order = [
            "id",
            "created",
            "message",
            "applied_scenario_names",
            "constrain_scenario_names",
            "required_scenario_names",
            "enabled_scenarios",
            "selected_scenario_names",
            "delivery_selection",
            "delivery_overrides",
            "delivery_selection",
            "selected_deliveries",
            "recipients_override",
            "delivered",
            "failed",
            "suppressed",
            "skipped",
            "error_count",
            "deliveries",
        ]
        # preferred fields
        result = {
            k: sanitize(
                self.__dict__[k], minimal=minimal, occupancy_only=True, top_level_keys_only=(minimal and k in keys_only)
            )
            for k in preferred_order
        }
        # all the rest not explicitly excluded
        result.update({
            k: sanitize(v, minimal=minimal, occupancy_only=True)
            for k, v in self.__dict__.items()
            if k not in result
            and k not in exposed_if_populated
            and k not in object_refs
            and not k.startswith("_")
            and (not minimal or k not in keys_only)
            and (not minimal or k not in debug_only)
        })
        # the exposed only if populated fields
        result.update({
            k: sanitize(self.__dict__[k], minimal=minimal, occupancy_only=True)
            for k in exposed_if_populated
            if self.__dict__.get(k)
        })
        return result

    def base_filename(self) -> str:
        """ArchiveableObject implementation"""
        return f"{self.created.isoformat()[:16]}_{self.id}"

    def delivery_data(self, delivery_name: str) -> dict[str, Any]:
        delivery_override: DeliveryCustomization | None = self.delivery_overrides.get(delivery_name)
        return delivery_override.data if delivery_override and delivery_override.data else {}

    @property
    def delivered_envelopes(self) -> list[Envelope]:
        result: list[Envelope] = []
        for delivery_result in self.deliveries.values():
            result.extend(cast("list[Envelope]", delivery_result.get(KEY_DELIVERED, [])))
        return result

    @property
    def undelivered_envelopes(self) -> list[Envelope]:
        result: list[Envelope] = []
        for delivery_result in self.deliveries.values():
            result.extend(cast("list[Envelope]", delivery_result.get(KEY_SUPPRESSED, [])))
            result.extend(cast("list[Envelope]", delivery_result.get(KEY_FAILED, [])))
        return result

    async def select_scenarios(self) -> list[str]:
        return [s.name for s in self.context.scenario_registry.scenarios.values() if s.evaluate(self.condition_variables)]

    def generate_targets(self, delivery: Delivery, recipients: list[str] | None = None) -> list[Target]:

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
        elif recipients is not None:
            computed_target = Target(recipients)
            self.debug_trace.record_target(delivery.name, "1a_delivery_default_fixed", computed_target)

        elif not self._target:
            # Unless there are explicit targets, include everyone on the people registry
            computed_target = self.default_person_ids(delivery)
            self.debug_trace.record_target(delivery.name, "2a_no_action_target", computed_target)
        else:
            computed_target = self._target.safe_copy()
            self.debug_trace.record_target(delivery.name, "2b_action_target", computed_target)

        # 1st round of filtering for snooze and resolving people->direct targets
        computed_target = self.context.snoozer.filter_recipients(computed_target, self.priority, delivery)
        self.debug_trace.record_target(delivery.name, "3a_post_snooze", computed_target)
        # turn person_ids into emails and phone numbers
        for indirect_target in self.resolve_indirect_targets(computed_target, delivery):
            computed_target += indirect_target
        self.debug_trace.record_target(delivery.name, "4a_resolve_indirect", computed_target)
        computed_target += self.resolve_scenario_targets(delivery)
        self.debug_trace.record_target(delivery.name, "5a_resolved_scenario_targets", computed_target)
        # filter out target not required for this delivery
        computed_target = delivery.select_targets(computed_target)
        self.debug_trace.record_target(delivery.name, "6a_delivery_selection", computed_target)
        primary_count = len(computed_target)

        if delivery.target_usage == TARGET_USE_ON_NO_DELIVERY_TARGETS:
            if not computed_target.has_targets() and delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "7a_delivery_default_no_delivery_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_ON_NO_ACTION_TARGETS:
            if not self._target and delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "7b_delivery_default_no_action_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_MERGE_ON_DELIVERY_TARGETS:
            # merge in the delivery defaults if there's a target defined in action call
            if computed_target.has_targets() and delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "7c_delivery_merge_on_delivery_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_MERGE_ALWAYS:
            # merge in the delivery defaults even if there's not a target defined in action call
            if delivery.target:
                computed_target += delivery.target
                self.debug_trace.record_target(delivery.name, "7d_delivery_merge_always_targets", computed_target)
        elif delivery.target_usage == TARGET_USE_FIXED:
            _LOGGER.debug("SUPERNOTIFY Fixed target on delivery %s", delivery.name)
            self.debug_trace.record_target(delivery.name, "7e_fixed_target", computed_target)
        else:
            self.debug_trace.record_target(delivery.name, "7f_no_target_usage_match", computed_target)
            _LOGGER.debug("SUPERNOTIFY No useful target definition for delivery %s", delivery.name)

        if len(computed_target) > primary_count:
            _LOGGER.debug(
                "SUPERNOTIFY Delivery config added %s targets for %s", len(computed_target) - primary_count, delivery.name
            )

            # 2nd round of filtering for snooze and resolving people->direct targets after delivery target applied
            computed_target = self.context.snoozer.filter_recipients(computed_target, self.priority, delivery)
            self.debug_trace.record_target(delivery.name, "8a_post_snooze", computed_target)
            for indirect_target in self.resolve_indirect_targets(computed_target, delivery):
                computed_target += indirect_target
            self.debug_trace.record_target(delivery.name, "9a_resolved_indirect_targets", computed_target)
            computed_target += self.resolve_scenario_targets(delivery)
            self.debug_trace.record_target(delivery.name, "10a_resolved_scenario_targets", computed_target)
            computed_target = delivery.select_targets(computed_target)
            self.debug_trace.record_target(delivery.name, "11a_delivery_selection", computed_target)

        split_targets: list[Target] = computed_target.split_by_target_data()
        self.debug_trace.record_target(delivery.name, "12_delivery_split_targets", split_targets)
        direct_targets: list[Target] = [t.direct() for t in split_targets]
        self.debug_trace.record_target(delivery.name, "13a_narrow_to_direct", direct_targets)
        if delivery.options.get(OPTION_UNIQUE_TARGETS, False):
            direct_targets = [t - self._already_selected for t in direct_targets]
            self.debug_trace.record_target(delivery.name, "14a_make_unique_across_deliveries", direct_targets)
        for direct_target in direct_targets:
            self._already_selected += direct_target
        self.debug_trace.record_target(delivery.name, "999_final_cut", direct_targets)
        return direct_targets

    def resolve_scenario_targets(self, delivery: Delivery) -> Target:
        resolved: Target = Target()
        for scenario in self.enabled_scenarios.values():
            customization: DeliveryCustomization | None = scenario.delivery_customization(delivery.name)
            if customization and customization.target and customization.target.has_targets():
                resolved += customization.target
        return resolved

    def all_recipients(self) -> list[Recipient]:
        recipients: list[Recipient] = []
        if self._target:
            # explicit targets given
            recipients.extend(
                self.people_registry.people[pers_ent_id]
                for pers_ent_id in self._target.person_ids
                if pers_ent_id in self.people_registry.people and self.people_registry.people[pers_ent_id].enabled
            )
        else:
            # default to all known recipients
            recipients = self.people_registry.enabled_recipients()
            recipients = [r for r in recipients if self.recipients_override is None or r.entity_id in self.recipients_override]
        return recipients

    def default_person_ids(self, delivery: Delivery) -> Target:
        # If target not specified on service call or delivery, then default to std list of recipients
        people: list[Recipient] = self.people_registry.filter_recipients_by_occupancy(delivery.occupancy)
        people = [p for p in people if self.recipients_override is None or p.entity_id in self.recipients_override]
        return Target({ATTR_PERSON_ID: [p.entity_id for p in people if p.entity_id]})

    def resolve_indirect_targets(self, target: Target, delivery: Delivery) -> list[Target]:
        # enrich data selected in configuration for this delivery, from direct target definition or attrs like email or phone
        resolved: Target = Target()
        additional: list[Target] = []

        for person_id in target.person_ids:
            recipient: Recipient | None = self.people_registry.people.get(person_id)
            if recipient and recipient.enabled:
                recipient_target = recipient.target(delivery.name)
                if recipient_target.target_specific_data:
                    additional.append(recipient_target)
                else:
                    resolved += recipient_target
            else:
                _LOGGER.debug("SUPERNOTIFY Skipping recipient %s with enabled switched off", person_id)

        return [resolved, *additional]

    def generate_envelopes(self, delivery: Delivery, targets: list[Target]) -> list[Envelope]:
        # now the list of recipients determined, resolve this to target addresses or entities

        envelopes: list[Envelope] = []
        for target in targets:
            # a target is always generated, even if there are no recipients
            if target.has_resolved_target() or delivery.target_required != TargetRequired.ALWAYS:
                envelope_data = {}
                envelope_data.update(delivery.data)
                envelope_data.update(self.extra_data)  # action call data
                if target.target_data:
                    envelope_data.update(target.target_data)
                # scenario applied at cross-delivery level in apply_enabled_scenarios
                for scenario in self.enabled_scenarios.values():
                    customization: DeliveryCustomization | None = scenario.delivery_customization(delivery.name)
                    if customization and customization.data:
                        envelope_data.update(customization.data)
                envelopes.append(Envelope(delivery, self, target, envelope_data, context=self.context))

        return envelopes
