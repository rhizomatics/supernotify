import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ENABLED
from homeassistant.helpers import issue_registry as ir

from . import (
    CONF_DATA,
    DELIVERY_SELECTION_IMPLICIT,
    DOMAIN,
    SCENARIO_DEFAULT,
    SCENARIO_TEMPLATE_ATTRS,
)
from .common import safe_get

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict

import voluptuous as vol
from homeassistant.components.trace import async_setup, async_store_trace  # type: ignore[attr-defined,unused-ignore]
from homeassistant.components.trace.const import DATA_TRACE
from homeassistant.components.trace.models import ActionTrace
from homeassistant.const import CONF_ALIAS, CONF_CONDITION
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import condition
from homeassistant.helpers.trace import trace_get, trace_path
from homeassistant.helpers.typing import ConfigType
from voluptuous import Invalid

from custom_components.supernotify.delivery import Delivery

from . import ATTR_DEFAULT, CONF_ACTION_GROUP_NAMES, CONF_DELIVERY, CONF_DELIVERY_SELECTION, CONF_MEDIA
from .model import ConditionVariables

_LOGGER = logging.getLogger(__name__)


class ScenarioRegistry:
    def __init__(self, scenario_configs: ConfigType, default_scenario_for_testing: bool = False) -> None:
        self._config: ConfigType = scenario_configs or {}
        self.scenarios: dict[str, Scenario] = {}
        self.content_scenario_templates: ConfigType = {}
        self.delivery_by_scenario: dict[str, list[str]] = {SCENARIO_DEFAULT: []}
        self.default_scenario_for_testing: bool = default_scenario_for_testing

    async def initialize(
        self,
        deliveries: dict[str, Delivery],
        default_deliveries: list[Delivery],
        mobile_actions: ConfigType,
        hass: HomeAssistant | None,
    ) -> None:
        for scenario_name, scenario_definition in self._config.items():
            scenario = Scenario(scenario_name, scenario_definition, hass)
            if await scenario.validate(valid_deliveries=list(deliveries), valid_action_groups=list(mobile_actions)):
                self.scenarios[scenario_name] = scenario
        self.refresh(deliveries, default_deliveries, self.default_scenario_for_testing)

    def refresh(
        self, deliveries: dict[str, Delivery], default_deliveries: list[Delivery], default_scenario: bool = False
    ) -> None:
        self.delivery_by_scenario = {}
        for scenario_name, scenario in self.scenarios.items():
            if scenario.enabled:
                self.delivery_by_scenario.setdefault(scenario_name, [])
                if scenario.delivery_selection == DELIVERY_SELECTION_IMPLICIT:
                    scenario_deliveries: list[str] = [d.name for d in default_deliveries]
                else:
                    scenario_deliveries = []
                scenario_definition_delivery = scenario.delivery
                scenario_deliveries.extend(s for s in scenario_definition_delivery if s not in scenario_deliveries)

                for scenario_delivery in scenario_deliveries:
                    if safe_get(scenario_definition_delivery.get(scenario_delivery), CONF_ENABLED, True):
                        if deliveries[scenario_delivery].enabled:
                            self.delivery_by_scenario[scenario_name].append(scenario_delivery)

                    scenario_delivery_config = safe_get(scenario_definition_delivery.get(scenario_delivery), CONF_DATA, {})

                    # extract message and title templates per scenario per delivery
                    for template_field in SCENARIO_TEMPLATE_ATTRS:
                        template_format = scenario_delivery_config.get(template_field)
                        if template_format is not None:
                            self.content_scenario_templates.setdefault(template_field, {})
                            self.content_scenario_templates[template_field].setdefault(scenario_delivery, [])
                            self.content_scenario_templates[template_field][scenario_delivery].append(scenario_name)

        self.delivery_by_scenario[SCENARIO_DEFAULT] = [d.name for d in default_deliveries]
        if default_scenario:
            for d in deliveries.values():
                if d.enabled and d.name not in self.delivery_by_scenario[SCENARIO_DEFAULT]:
                    self.delivery_by_scenario[SCENARIO_DEFAULT].append(d.name)


class Scenario:
    def __init__(self, name: str, scenario_definition: dict[str, Any], hass: HomeAssistant | None) -> None:
        self.hass: HomeAssistant | None = hass
        self.enabled: bool = scenario_definition.get(CONF_ENABLED, True)
        self.name: str = name
        self.alias: str | None = scenario_definition.get(CONF_ALIAS)
        self.condition: ConfigType | None = scenario_definition.get(CONF_CONDITION)
        self.media: dict[str, Any] | None = scenario_definition.get(CONF_MEDIA)
        self.delivery_selection: str | None = scenario_definition.get(CONF_DELIVERY_SELECTION)
        self.action_groups: list[str] = scenario_definition.get(CONF_ACTION_GROUP_NAMES, [])
        self.delivery: dict[str, Any] = scenario_definition.get(CONF_DELIVERY) or {}
        self.default: bool = self.name == ATTR_DEFAULT
        self.last_trace: ActionTrace | None = None
        self.condition_func = None

    async def validate(self, valid_deliveries: list[str] | None = None, valid_action_groups: list[str] | None = None) -> bool:
        """Validate Home Assistant conditiion definition at initiation"""
        if self.condition and self.hass:
            error: str | None = None
            try:
                # note: basic template syntax within conditions already validated by voluptuous checks
                cond: ConfigType = await condition.async_validate_condition_config(self.hass, self.condition)
                self.force_strict_template_mode(cond, undo=False)
                test: condition.ConditionCheckerType = await condition.async_from_config(self.hass, cond)
                test(self.hass, asdict(ConditionVariables()))
                self.force_strict_template_mode(cond, undo=True)
            except vol.Invalid as vi:
                _LOGGER.error(
                    f"SUPERNOTIFY Condition definition for scenario {self.name} fails Home Assistant schema check {vi}"
                )
                error = f"Schema error {vi}"
            except Exception as e:
                _LOGGER.error("SUPERNOTIFY Disabling scenario %s with error validating %s: %s", self.name, self.condition, e)
                error = f"Unknown error {e}"
            if error is not None:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"scenario_{self.name}_condition",
                    is_fixable=False,
                    translation_key="scenario_condition",
                    translation_placeholders={"scenario": self.name, "error": error},
                    severity=ir.IssueSeverity.ERROR,
                    learn_more_url="https://supernotify.rhizomatics.github.io/#scenarios",
                )
                return False

        if valid_deliveries is not None:
            invalid_deliveries: list[str] = []
            for delivery_name in self.delivery:
                if delivery_name not in valid_deliveries:
                    _LOGGER.error(f"SUPERNOTIFY Unknown delivery {delivery_name} removed from scenario {self.name}")
                    invalid_deliveries.append(delivery_name)
                    if self.hass:
                        ir.async_create_issue(
                            self.hass,
                            DOMAIN,
                            f"scenario_{self.name}_delivery_{delivery_name}",
                            is_fixable=False,
                            translation_key="scenario_delivery",
                            translation_placeholders={"scenario": self.name, "delivery": delivery_name},
                            severity=ir.IssueSeverity.WARNING,
                            learn_more_url="https:/supernotify.rhizomatics.github.io/#scenarios",
                        )
            for delivery_name in invalid_deliveries:
                del self.delivery[delivery_name]

        if valid_action_groups is not None:
            invalid_action_groups: list[str] = []
            for action_group_name in self.action_groups:
                if action_group_name not in valid_action_groups:
                    _LOGGER.error(f"SUPERNOTIFY Unknown delivery {action_group_name} removed from scenario {self.name}")
                    invalid_action_groups.append(action_group_name)
                    if self.hass:
                        ir.async_create_issue(
                            self.hass,
                            DOMAIN,
                            f"scenario_{self.name}_action_group_{action_group_name}",
                            is_fixable=False,
                            translation_key="scenario_delivery",
                            translation_placeholders={"scenario": self.name, "action_group": action_group_name},
                            severity=ir.IssueSeverity.WARNING,
                            learn_more_url="https://supernotify.rhizomatics.github.io/#scenarios",
                        )
            for action_group_name in invalid_action_groups:
                self.action_groups.remove(action_group_name)
        return True

    def force_strict_template_mode(self, condition: ConfigType, undo: bool = False) -> None:
        from functools import partial

        from homeassistant.helpers.template import Template

        class TemplateWrapper:
            def __init__(self, obj: Template) -> None:
                self._obj = obj

            def __getattr__(self, name: str) -> Any:
                if name == "async_render_to_info":
                    return partial(self._obj.async_render_to_info, strict=True)
                return getattr(self._obj, name)

            def __setattr__(self, name: str, value: Any) -> None:
                super().__setattr__(name, value)

        def wrap_template(cond: ConfigType, undo: bool) -> None:
            for key, val in cond.items():
                if not undo and isinstance(val, Template) and hasattr(val, "_env"):
                    cond[key] = TemplateWrapper(val)
                elif undo and isinstance(val, TemplateWrapper):
                    cond[key] = val._obj
                elif isinstance(val, dict):
                    wrap_template(val, undo)

        if condition is not None:
            wrap_template(condition, undo)

    def attributes(self, include_condition: bool = True, include_trace: bool = False) -> dict[str, Any]:
        """Return scenario attributes"""
        attrs = {
            "name": self.name,
            "enabled": self.enabled,
            "alias": self.alias,
            "media": self.media,
            "delivery_selection": self.delivery_selection,
            "action_groups": self.action_groups,
            "delivery": self.delivery,
            "default": self.default,
        }
        if include_condition:
            attrs["condition"] = self.condition
        if include_trace and self.last_trace:
            attrs["trace"] = self.last_trace.as_extended_dict()
        return attrs

    def contents(self, minimal: bool = False) -> dict[str, Any]:
        """Archive friendly view of scenario"""
        return self.attributes(include_condition=False, include_trace=not minimal)

    async def evaluate(self, condition_variables: ConditionVariables | None = None) -> bool:
        """Evaluate scenario conditions"""
        if not self.enabled:
            return False
        if self.condition and self.hass:
            try:
                test = await condition.async_from_config(self.hass, self.condition)
                if test is None:
                    raise Invalid(f"Empty condition generated for {self.name}")
            except Exception as e:
                _LOGGER.error("SUPERNOTIFY Scenario %s condition create failed: %s", self.name, e)
                return False
            try:
                if test(self.hass, asdict(condition_variables) if condition_variables else None):
                    return True
            except Exception as e:
                _LOGGER.error(
                    "SUPERNOTIFY Scenario condition eval failed: %s, vars: %s",
                    e,
                    condition_variables.as_dict() if condition_variables else {},
                )
        return False

    async def trace(self, condition_variables: ConditionVariables | None = None, config: ConfigType | None = None) -> bool:
        """Trace scenario delivery"""
        result = None
        config = {} if config is None else config
        if not self.hass:
            return False
        if DATA_TRACE not in self.hass.data:
            await async_setup(self.hass, config)
        with trace_action(self.hass, f"scenario_{self.name}", config) as scenario_trace:
            scenario_trace.set_trace(trace_get())
            self.last_trace = scenario_trace
            with trace_path(["condition", "conditions"]) as _tp:
                result = await self.evaluate(condition_variables)
            _LOGGER.info(scenario_trace.as_dict())
        return result


@contextmanager
def trace_action(
    hass: HomeAssistant,
    item_id: str,
    config: dict[str, Any],
    context: Context | None = None,
    stored_traces: int = 5,
) -> Iterator[ActionTrace]:
    """Trace execution of a scenario."""
    trace = ActionTrace(item_id, config, None, context or Context())
    async_store_trace(hass, trace, stored_traces)

    try:
        yield trace
    except Exception as ex:
        if item_id:
            trace.set_error(ex)
        raise
    finally:
        if item_id:
            trace.finished()
