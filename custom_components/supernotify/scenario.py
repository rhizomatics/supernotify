from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ENABLED, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.helpers import condition
from homeassistant.helpers import issue_registry as ir

from custom_components.supernotify.people import PeopleRegistry

from . import DOMAIN
from .common import sanitize
from .const import (
    ATTR_MEDIA,
    CONF_EXPOSE_STATE,
    CONF_REFRESH,
    CONF_REFRESH_INTERVAL,
    PRIORITY_MEDIUM,
    SCENARIO_STATE_REFRESH_DEFAULT,
)
from .model import DeliveryCustomization

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import State
    from homeassistant.helpers.typing import ConfigType

    from .delivery import Delivery, DeliveryRegistry
    from .hass_api import HomeAssistantAPI
    from .schema import ConditionsFunc

from contextlib import contextmanager

import voluptuous as vol

# type: ignore[attr-defined,unused-ignore]
from homeassistant.components.trace import async_store_trace
from homeassistant.components.trace.models import ActionTrace
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_NAME, CONF_ALIAS, CONF_CONDITIONS
from homeassistant.core import Context

from .const import ATTR_ENABLED, CONF_ACTION_GROUP_NAMES, CONF_DELIVERY, CONF_MEDIA
from .model import ConditionVariables

_LOGGER = logging.getLogger(__name__)


class ScenarioRegistry:
    def __init__(
        self, scenario_configs: ConfigType, scenario_control: ConfigType | None, people_registry: PeopleRegistry
    ) -> None:
        self._config: ConfigType = scenario_configs or {}
        self.scenarios: dict[str, Scenario] = {}
        self.scenario_control = scenario_control or {}
        self._people_registry: PeopleRegistry = people_registry

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
        self._hass_api: HomeAssistantAPI = hass_api
        self._scenario_cond_entities = self._collect_scenario_condition_entities()
        self._scenario_by_entity = self._index_scenarios_by_entity()

        # Keep the scenario binary_sensors' state current: react to their condition entities
        # (immediate, and only for the scenarios that depend on the entity that changed), plus
        # a periodic sweep for conditions no entity change announces - time windows, sun, and
        # templates whose dependencies could not be extracted.
        # Evaluating conditions costs whatever the conditions cost, so the whole mechanism is
        # switchable: `scenario_control: {enabled: false}` subscribes to nothing and starts no
        # timer, and `refresh_interval: 0` keeps the reactive path without the sweep.
        if self.scenario_state_enabled:
            scenario_watch: set[str] = set(self._scenario_by_entity)
            if scenario_watch:
                hass_api.subscribe_state(sorted(scenario_watch), self.async_refresh_scenario_states)
            if self.scenario_state_interval:
                hass_api.subscribe_interval(self.scenario_state_interval, self.async_refresh_scenario_states)

    def expose_entities(self, hass_api: HomeAssistantAPI) -> None:
        for scenario in self.scenarios.values():
            hass_api.expose_entity(
                f"scenario_{scenario.name}",
                state=self._scenario_state(scenario),
                attributes=sanitize(scenario.attributes(include_condition=False)),
                original_name=f"{scenario.name} Scenario",
                original_icon="mdi:clipboard-text",
            )

    def handle_entity_state_change(self, entity_id: str, new_state: State) -> bool | None:
        """React to a scenario binary_sensor being toggled on/off.

        Returns None if entity_id isn't one of ours, True if it was recognised and its
        enabled state changed, False if recognised but unknown or already in that state.
        """
        prefix = f"binary_sensor.{DOMAIN}_scenario_"
        if not entity_id.startswith(prefix):
            return None

        scenario = self.scenarios.get(entity_id.removeprefix(prefix))
        if scenario is None:
            _LOGGER.warning("SUPERNOTIFY Event for unknown scenario %s", entity_id)
            return False
        if new_state.state == STATE_OFF and scenario.enabled:
            scenario.enabled = False
            _LOGGER.info("SUPERNOTIFY Disabling scenario %s", scenario.name)
            return True
        if new_state.state == STATE_ON and not scenario.enabled:
            scenario.enabled = True
            _LOGGER.info("SUPERNOTIFY Enabling scenario %s", scenario.name)
            return True
        _LOGGER.info("SUPERNOTIFY No change to scenario %s, already %s", scenario.name, new_state)
        return False

    def _collect_scenario_condition_entities(self) -> dict[str, set[str]]:
        """Entities referenced by each scenario's conditions.

        A scenario whose conditions reference no Home Assistant entity depends
        only on the per-notification variables (notification_priority /
        applied_scenarios). Such a scenario is 'transient': it has no meaningful
        state between notifications, so it is left as STATE_UNKNOWN. Extraction is
        best-effort (templates are opaque); the periodic refresh is the safety net.
        """
        mapping: dict[str, set[str]] = {}
        for name, scenario in self.scenarios.items():
            ents: set[str] = set()
            for cond in scenario.conditions_config or []:
                try:
                    ents |= condition.async_extract_entities(cond)
                except Exception:
                    _LOGGER.debug("SUPERNOTIFY could not extract entities for scenario %s", name)
            mapping[name] = ents
        return mapping

    @property
    def scenario_state_enabled(self) -> bool:
        return bool(self.scenario_control.get(CONF_REFRESH, True))

    @property
    def scenario_state_interval(self) -> int:
        return int(self.scenario_control.get(CONF_REFRESH_INTERVAL, SCENARIO_STATE_REFRESH_DEFAULT))

    def _index_scenarios_by_entity(self) -> dict[str, set[str]]:
        """Reverse of _collect_scenario_condition_entities: entity -> scenarios depending on it.

        Used to re-evaluate only the scenarios a state change can actually affect, instead of
        the whole registry on every event.
        """
        index: dict[str, set[str]] = {}
        for name, entities in self._scenario_cond_entities.items():
            scenario = self.scenarios.get(name)
            if scenario is not None and not scenario.expose_state:
                continue
            for entity_id in entities:
                index.setdefault(entity_id, set()).add(name)
        return index

    def _scenario_state(self, scenario: Scenario, cvars: ConditionVariables | None = None) -> str:
        """State to expose for a scenario binary_sensor.

        - no conditions, or conditions with no source entity -> transient/manual
          -> STATE_UNKNOWN (state is undefined outside of a notification);
        - otherwise ON/OFF from a neutral evaluation (current occupancy, medium
          priority), the same basis as enquire_active_scenarios().
        """
        if not scenario.expose_state:
            return STATE_UNKNOWN
        if not scenario.conditions_config:
            return STATE_UNKNOWN
        if not getattr(self, "_scenario_cond_entities", {}).get(scenario.name):
            return STATE_UNKNOWN
        if cvars is None:
            occupiers = self._people_registry.determine_occupancy()
            cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, occupiers, None, None)
        return STATE_ON if scenario.evaluate(cvars) else STATE_OFF

    @callback
    def async_refresh_scenario_states(self, *args: Any) -> None:
        """Re-evaluate and re-publish the state of every scenario binary_sensor.

        Triggered by the 1-minute timer (time/date scenarios and any dependency
        not captured by entity extraction) and by state changes of the scenarios'
        condition entities (immediate reactivity). Pure in-memory evaluation over
        cached states; no I/O.
        """
        if not self.scenario_state_enabled:
            return
        names: set[str] | None = None
        if args:
            event = args[0]
            entity_id = getattr(event, "data", {}).get("entity_id") if hasattr(event, "data") else None
            if entity_id is not None:
                names = self._scenario_by_entity.get(entity_id, set())
                if not names:
                    return

        occupiers = self._people_registry.determine_occupancy()
        cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, occupiers, None, None)
        for name, scenario in self.scenarios.items():
            if names is not None and name not in names:
                continue
            self._hass_api.set_state(
                f"binary_sensor.{DOMAIN}_scenario_{name}",
                self._scenario_state(scenario, cvars),
                sanitize(scenario.attributes(include_condition=False)),
            )


class Scenario:
    def __init__(
        self, name: str, scenario_definition: dict[str, Any], delivery_registry: DeliveryRegistry, hass_api: HomeAssistantAPI
    ) -> None:
        self.hass_api: HomeAssistantAPI = hass_api
        self.delivery_registry = delivery_registry
        self.enabled: bool = scenario_definition.get(CONF_ENABLED, True)
        self.expose_state: bool = scenario_definition.get(CONF_EXPOSE_STATE, True)
        self.name: str = name
        self.alias: str | None = scenario_definition.get(CONF_ALIAS)
        self.conditions: ConditionsFunc | None = None
        self.conditions_config: list[ConfigType] | None = scenario_definition.get(CONF_CONDITIONS)
        self.media: dict[str, Any] | None = scenario_definition.get(CONF_MEDIA)
        self.action_groups: list[str] = scenario_definition.get(CONF_ACTION_GROUP_NAMES, [])
        self._config_delivery: dict[str, DeliveryCustomization]
        self.delivery_overrides: dict[str, DeliveryCustomization] = {}
        self._delivery_selector: dict[str, str] = {}
        self.last_trace: ActionTrace | None = None
        self.startup_issue_count: int = 0

        delivery_data = scenario_definition.get(CONF_DELIVERY)
        if isinstance(delivery_data, list):
            # a bare list of deliveries implies enabling
            _LOGGER.debug("SUPERNOTIFY Scenario %s delivery default enabled for list %s", self.name, delivery_data)
            self._config_delivery = {k: DeliveryCustomization(config=None, default_enabled=True) for k in delivery_data}
        elif isinstance(delivery_data, str) and delivery_data:
            # a bare list of deliveries implies enabled delivery
            _LOGGER.debug("SUPERNOTIFY Scenario %s delivery default enabled for single %s", self.name, delivery_data)
            self._config_delivery = {delivery_data: DeliveryCustomization(config=None, default_enabled=True)}
        elif isinstance(delivery_data, dict):
            # whereas a dict may be used to tune or restrict
            _LOGGER.debug("SUPERNOTIFY Scenario %s delivery selection %s", self.name, delivery_data)
            self._config_delivery = {}
            for k, v in delivery_data.items():
                # a wildcard/regex pattern with no explicit enabled: only apply as an
                # override to deliveries already selected elsewhere, don't force-enable
                # every delivery it happens to match (e.g. selection: scenario deliveries)
                self._config_delivery[k] = DeliveryCustomization(
                    config=v, default_enabled=True if k in delivery_registry.deliveries else None
                )
        elif delivery_data:
            _LOGGER.warning("SUPERNOTIFY Unable to interpret scenario %s delivery data %s", self.name, delivery_data)
            self._config_delivery = {}
        else:
            _LOGGER.warning("SUPERNOTIFY No delivery definitions for scenario %s", self.name)
            self._config_delivery = {}

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
                self.delivery_overrides[delivery.name] = config
                self._delivery_selector[delivery.name] = name_or_pattern
                matched = True
            else:
                # look for a wildcard match instead
                for delivery_name in self.delivery_registry.deliveries:
                    if re.fullmatch(name_or_pattern, delivery_name):
                        if self._delivery_selector.get(delivery_name) == delivery_name:
                            _LOGGER.info(
                                f"SUPERNOTIFY Scenario {self.name} ignoring '{name_or_pattern}' shadowing explicit delivery {delivery_name}"
                            )
                        else:
                            _LOGGER.debug(
                                f"SUPERNOTIFY Scenario {self.name} delivery '{name_or_pattern}' matched {delivery_name}"
                            )
                            self.delivery_overrides[delivery_name] = config
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
        # default_enabled (see __init__/DeliveryCustomization) already resolves whether an
        # omitted `enabled` key should count as enabling: True for a directly-named delivery
        # (matching the list/string delivery config forms), None for a wildcard/regex match
        # so it doesn't force-select every delivery it happens to match. An explicit
        # `enabled: None` (e.g. just to carry a priority override) is left as None too, not
        # upgraded to the default - only a real `enabled: true` should land here.
        return [del_name for del_name, del_config in self.delivery_overrides.items() if del_config.enabled is True]

    def relevant_deliveries(self) -> list[str]:
        return [
            del_name
            for del_name, del_config in self.delivery_overrides.items()
            if del_config.enabled or del_config.enabled is None
        ]

    def disabling_deliveries(self) -> list[str]:
        return [del_name for del_name, del_config in self.delivery_overrides.items() if del_config.enabled is False]

    def delivery_customization(self, delivery_name: str) -> DeliveryCustomization | None:
        return self.delivery_overrides.get(delivery_name)

    def attributes(self, include_condition: bool = True, include_trace: bool = False) -> dict[str, Any]:
        """Return scenario attributes"""
        attrs = {
            ATTR_NAME: self.name,
            ATTR_ENABLED: self.enabled,
            ATTR_MEDIA: self.media,
            "action_groups": self.action_groups,
            "delivery": self.delivery_overrides,
        }
        if self.alias:
            attrs[ATTR_FRIENDLY_NAME] = self.alias
        if include_condition:
            attrs["conditions"] = self.conditions_config
        if include_trace and self.last_trace:
            attrs["trace"] = self.last_trace.as_extended_dict()
        return attrs

    def delivery_config(self, delivery_name: str) -> DeliveryCustomization | None:
        return self.delivery_overrides.get(delivery_name)

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
                    _LOGGER.warning(f"SUPERNOTIFY Scenario {self.name} condition empty result")
            except Exception as e:
                _LOGGER.error(
                    "SUPERNOTIFY Scenario %s condition eval failed: %s, vars: %s",
                    self.name,
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
