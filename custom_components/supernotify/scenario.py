import logging
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ENABLED
from homeassistant.helpers import issue_registry as ir

from . import (
    CONF_DATA,
    DELIVERY_SELECTION_IMPLICIT,
    SCENARIO_TEMPLATE_ATTRS,
)
from .common import safe_get
from .hass_api import HomeAssistantAPI

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


from collections.abc import Iterator
from contextlib import contextmanager

import voluptuous as vol

# type: ignore[attr-defined,unused-ignore]
from homeassistant.components.trace import async_store_trace
from homeassistant.components.trace.models import ActionTrace
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_NAME, CONF_ALIAS, CONF_CONDITION
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import ATTR_DEFAULT, ATTR_ENABLED, CONF_ACTION_GROUP_NAMES, CONF_DELIVERY, CONF_DELIVERY_SELECTION, CONF_MEDIA
from .delivery import Delivery
from .model import ConditionVariables

_LOGGER = logging.getLogger(__name__)


class ScenarioRegistry:
    def __init__(self, scenario_configs: ConfigType | None = None) -> None:
        self._config: ConfigType = scenario_configs or {}
        self.scenarios: dict[str, Scenario] = {}
        self.content_scenario_templates: ConfigType = {}
        self.delivery_by_scenario: dict[str, list[str]] = {}

    async def initialize(
        self,
        deliveries: dict[str, Delivery],
        implicit_deliveries: list[Delivery],
        mobile_actions: ConfigType,
        hass_api: HomeAssistantAPI,
    ) -> None:
        for scenario_name, scenario_definition in self._config.items():
            scenario = Scenario(scenario_name, scenario_definition, hass_api)
            if await scenario.validate(valid_deliveries=list(deliveries), valid_action_groups=list(mobile_actions)):
                self.scenarios[scenario_name] = scenario
        self.refresh(deliveries, implicit_deliveries)

    def refresh(self, deliveries: dict[str, Delivery], implicit_deliveries: list[Delivery]) -> None:
        self.delivery_by_scenario = {}
        for scenario_name, scenario in self.scenarios.items():
            if scenario.enabled:
                self.delivery_by_scenario.setdefault(scenario_name, [])
                if scenario.delivery_selection == DELIVERY_SELECTION_IMPLICIT:
                    scenario_deliveries: list[str] = [d.name for d in implicit_deliveries]
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


class Scenario:
    def __init__(self, name: str, scenario_definition: dict[str, Any], hass_api: HomeAssistantAPI) -> None:
        self.hass_api: HomeAssistantAPI = hass_api
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
        if self.condition:
            error: str | None = None
            try:
                # note: basic template syntax within conditions already validated by voluptuous checks
                await self.hass_api.evaluate_condition(self.condition, ConditionVariables(), strict=True, validate=True)
            except vol.Invalid as vi:
                _LOGGER.error(
                    f"SUPERNOTIFY Condition definition for scenario {self.name} fails Home Assistant schema check {vi}"
                )
                error = f"Schema error {vi}"
            except Exception as e:
                _LOGGER.error("SUPERNOTIFY Disabling scenario %s with error validating %s: %s", self.name, self.condition, e)
                error = f"Unknown error {e}"
            if error is not None:
                self.hass_api.raise_issue(
                    f"scenario_{self.name}_condition",
                    is_fixable=False,
                    issue_key="scenario_condition",
                    issue_map={"scenario": self.name, "error": error},
                    severity=ir.IssueSeverity.ERROR,
                    learn_more_url="https://supernotify.rhizomatics.org.uk/scenarios/",
                )
                return False

        if valid_deliveries is not None:
            invalid_deliveries: list[str] = []
            for delivery_name in self.delivery:
                if delivery_name not in valid_deliveries:
                    _LOGGER.error(f"SUPERNOTIFY Unknown delivery {delivery_name} removed from scenario {self.name}")
                    invalid_deliveries.append(delivery_name)
                    self.hass_api.raise_issue(
                        f"scenario_{self.name}_delivery_{delivery_name}",
                        is_fixable=False,
                        issue_key="scenario_delivery",
                        issue_map={"scenario": self.name, "delivery": delivery_name},
                        severity=ir.IssueSeverity.WARNING,
                        learn_more_url="https://supernotify.rhizomatics.org.uk/scenarios/",
                    )
            for delivery_name in invalid_deliveries:
                del self.delivery[delivery_name]

        if valid_action_groups is not None:
            invalid_action_groups: list[str] = []
            for action_group_name in self.action_groups:
                if action_group_name not in valid_action_groups:
                    _LOGGER.error(f"SUPERNOTIFY Unknown action group {action_group_name} removed from scenario {self.name}")
                    invalid_action_groups.append(action_group_name)
                    self.hass_api.raise_issue(
                        f"scenario_{self.name}_action_group_{action_group_name}",
                        is_fixable=False,
                        issue_key="scenario_delivery",
                        issue_map={"scenario": self.name, "action_group": action_group_name},
                        severity=ir.IssueSeverity.WARNING,
                        learn_more_url="https://supernotify.rhizomatics.org.uk/scenarios/",
                    )
            for action_group_name in invalid_action_groups:
                self.action_groups.remove(action_group_name)
        return True

    def attributes(self, include_condition: bool = True, include_trace: bool = False) -> dict[str, Any]:
        """Return scenario attributes"""
        attrs = {
            ATTR_NAME: self.name,
            ATTR_ENABLED: self.enabled,
            "media": self.media,
            "delivery_selection": self.delivery_selection,
            "action_groups": self.action_groups,
            "delivery": self.delivery,
            "default": self.default,
        }
        if self.alias:
            attrs[ATTR_FRIENDLY_NAME] = self.alias
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
        result: bool | None = False
        if self.enabled and self.condition:
            try:
                result = await self.hass_api.evaluate_condition(self.condition, condition_variables)
                if result is None:
                    _LOGGER.warning("SUPERNOTIFY Scenario condition empty result")
            except Exception as e:
                _LOGGER.error(
                    "SUPERNOTIFY Scenario condition eval failed: %s, vars: %s",
                    e,
                    condition_variables.as_dict() if condition_variables else {},
                )
        return result if result is not None else False

    async def trace(
        self, condition_variables: ConditionVariables | None = None, strict: bool = False, validate: bool = False
    ) -> bool:
        """Trace scenario condition execution"""
        result: bool | None = False
        trace: ActionTrace | None = None
        if self.enabled and self.condition:
            result, trace = await self.hass_api.trace_condition(
                self.condition, condition_variables, strict=strict, validate=validate, trace_name=f"scenario_{self.name}"
            )
            if trace:
                self.last_trace = trace
        return result if result is not None else False


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
