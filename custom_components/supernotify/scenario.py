import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ENABLED
from homeassistant.helpers import issue_registry as ir

from . import ConditionsFunc
from .hass_api import HomeAssistantAPI
from .model import DeliveryCustomization

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

from collections.abc import Iterator
from contextlib import contextmanager

import voluptuous as vol

# type: ignore[attr-defined,unused-ignore]
from homeassistant.components.trace import async_store_trace
from homeassistant.components.trace.models import ActionTrace
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_NAME, CONF_ALIAS, CONF_CONDITION, CONF_CONDITIONS
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from . import ATTR_ENABLED, CONF_ACTION_GROUP_NAMES, CONF_DELIVERY, CONF_MEDIA
from .delivery import Delivery, DeliveryRegistry
from .model import ConditionVariables

_LOGGER = logging.getLogger(__name__)


class ScenarioRegistry:
    def __init__(self, scenario_configs: ConfigType) -> None:
        self._config: ConfigType = scenario_configs or {}
        self.scenarios: dict[str, Scenario] = {}

    async def initialize(
        self,
        delivery_registry: DeliveryRegistry,
        mobile_actions: ConfigType,
        hass_api: HomeAssistantAPI,
    ) -> None:

        for scenario_name, scenario_definition in self._config.items():
            scenario = Scenario(scenario_name, scenario_definition, delivery_registry, hass_api)
            if await scenario.validate(valid_action_group_names=list(mobile_actions)):
                self.scenarios[scenario_name] = scenario
            else:
                _LOGGER.warning("SUPERNOTIFY Scenario %s failed to validate, ignoring", scenario.name)


class Scenario:
    def __init__(
        self, name: str, scenario_definition: dict[str, Any], delivery_registry: DeliveryRegistry, hass_api: HomeAssistantAPI
    ) -> None:
        self.hass_api: HomeAssistantAPI = hass_api
        self.delivery_registry = delivery_registry
        self.enabled: bool = scenario_definition.get(CONF_ENABLED, True)
        self.name: str = name
        self.alias: str | None = scenario_definition.get(CONF_ALIAS)
        self.conditions: ConditionsFunc | None = None
        self.conditions_config: list[ConfigType] | None = scenario_definition.get(CONF_CONDITIONS)
        if not scenario_definition.get(CONF_CONDITIONS) and scenario_definition.get(CONF_CONDITION):
            self.conditions_config = scenario_definition.get(CONF_CONDITION)
        self.media: dict[str, Any] | None = scenario_definition.get(CONF_MEDIA)
        self.action_groups: list[str] = scenario_definition.get(CONF_ACTION_GROUP_NAMES, [])
        self._config_delivery: dict[str, DeliveryCustomization] = {
            k: DeliveryCustomization(v) for k, v in scenario_definition.get(CONF_DELIVERY, {}).items()
        }
        self.delivery: dict[str, DeliveryCustomization] = {}
        self._delivery_selector: dict[str, str] = {}
        self.last_trace: ActionTrace | None = None
        self.startup_issue_count: int = 0

    async def validate(self, valid_action_group_names: list[str] | None = None) -> bool:
        """Validate Home Assistant conditiion definition at initiation"""
        if self.conditions_config:
            error: str | None = None
            try:
                # note: basic template syntax within conditions already validated by voluptuous checks
                self.conditions = await self.hass_api.build_conditions(self.conditions_config, strict=True, validate=True)
            except vol.Invalid as vi:
                _LOGGER.error(
                    f"SUPERNOTIFY Condition definition for scenario {self.name} fails Home Assistant schema check {vi}"
                )
                error = f"Schema error {vi}"
            except Exception as e:
                _LOGGER.error(
                    "SUPERNOTIFY Disabling scenario %s with error validating %s: %s", self.name, self.conditions_config, e
                )
                error = f"Unknown error {e}"
            if error is not None:
                self.startup_issue_count += 1
                self.hass_api.raise_issue(
                    f"scenario_{self.name}_condition",
                    is_fixable=False,
                    issue_key="scenario_condition",
                    issue_map={"scenario": self.name, "error": error},
                    severity=ir.IssueSeverity.ERROR,
                    learn_more_url="https://supernotify.rhizomatics.org.uk/scenarios/",
                )

        for name_or_pattern, config in self._config_delivery.items():
            matched: bool = False
            delivery: Delivery | None = self.delivery_registry.deliveries.get(name_or_pattern)
            if delivery:
                self.delivery[delivery.name] = config
                self._delivery_selector[delivery.name] = name_or_pattern
                matched = True
            else:
                # look for a wildcard match instead
                for delivery_name in self.delivery_registry.deliveries:
                    if re.fullmatch(name_or_pattern, delivery_name):
                        if self._delivery_selector.get(delivery_name) == delivery_name:
                            _LOGGER.info(
                                f"SUPERNOTIFY Scenario {self.name} ignoring '{name_or_pattern}' shadowing explicit delivery {delivery_name}"  # noqa: E501
                            )
                        else:
                            _LOGGER.debug(f"SUPERNOTIFY Scenario delivery '{name_or_pattern}' matched {delivery_name}")
                            self.delivery[delivery_name] = config
                            self._delivery_selector[delivery_name] = name_or_pattern
                            matched = True
            if not matched:
                _LOGGER.error(f"SUPERNOTIFY Scenario {self.name} has delivery {name_or_pattern} not found")
                self.startup_issue_count += 1
                self.hass_api.raise_issue(
                    f"scenario_{self.name}_delivery_{name_or_pattern.replace('.', 'DOT').replace('*', 'STAR')}",
                    is_fixable=False,
                    issue_key="scenario_delivery",
                    issue_map={"scenario": self.name, "delivery": name_or_pattern},
                    severity=ir.IssueSeverity.WARNING,
                    learn_more_url="https://supernotify.rhizomatics.org.uk/scenarios/",
                )

        if valid_action_group_names is not None:
            invalid_action_groups: list[str] = []
            for action_group_name in self.action_groups:
                if action_group_name not in valid_action_group_names:
                    _LOGGER.error(f"SUPERNOTIFY Unknown action group {action_group_name} removed from scenario {self.name}")
                    invalid_action_groups.append(action_group_name)
                    self.startup_issue_count += 1
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

        return self.startup_issue_count == 0

    def enabling_deliveries(self) -> list[str]:
        return [del_name for del_name, del_config in self.delivery.items() if del_config.enabled]

    def relevant_deliveries(self) -> list[str]:
        return [del_name for del_name, del_config in self.delivery.items() if del_config.enabled or del_config is None]

    def disabling_deliveries(self) -> list[str]:
        return [del_name for del_name, del_config in self.delivery.items() if del_config.enabled is False]

    def delivery_customization(self, delivery_name: str) -> DeliveryCustomization | None:
        return self.delivery.get(delivery_name)

    def attributes(self, include_condition: bool = True, include_trace: bool = False) -> dict[str, Any]:
        """Return scenario attributes"""
        attrs = {
            ATTR_NAME: self.name,
            ATTR_ENABLED: self.enabled,
            "media": self.media,
            "action_groups": self.action_groups,
            "delivery": {k: v.as_dict() for k, v in self.delivery.items()},
        }
        if self.alias:
            attrs[ATTR_FRIENDLY_NAME] = self.alias
        if include_condition:
            attrs["conditions"] = self.conditions
        if include_trace and self.last_trace:
            attrs["trace"] = self.last_trace.as_extended_dict()
        return attrs

    def delivery_config(self, delivery_name: str) -> DeliveryCustomization | None:
        return self.delivery.get(delivery_name)

    def contents(self, minimal: bool = False, **_kwargs: Any) -> dict[str, Any]:
        """Archive friendly view of scenario"""
        return self.attributes(include_condition=False, include_trace=not minimal)

    def evaluate(self, condition_variables: ConditionVariables) -> bool:
        """Evaluate scenario conditions"""
        result: bool | None = False
        if self.enabled and self.conditions:
            try:
                result = self.hass_api.evaluate_conditions(self.conditions, condition_variables)
                if result is None:
                    _LOGGER.warning("SUPERNOTIFY Scenario condition empty result")
            except Exception as e:
                _LOGGER.error(
                    "SUPERNOTIFY Scenario condition eval failed: %s, vars: %s",
                    e,
                    condition_variables.as_dict() if condition_variables else {},
                )
        return result if result is not None else False

    async def trace(self, condition_variables: ConditionVariables) -> bool:
        """Trace scenario condition execution"""
        result: bool | None = False
        trace: ActionTrace | None = None
        if self.enabled and self.conditions:
            result, trace = await self.hass_api.trace_conditions(
                self.conditions, condition_variables, trace_name=f"scenario_{self.name}"
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
