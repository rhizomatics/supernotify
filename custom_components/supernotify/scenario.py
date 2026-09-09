# CHANGELOG
# 2026-09-08 (Claude): fix bug alta severità #2 e #3 + bug medio dalla review multi-agente del
# branch feat/native-entities-scenario-recipient-counters (vedi memoria di progetto
# project_native_entities_review_202609.md), prima di proporlo come PR upstream:
# - ScenarioRegistry._pending_first_publish (nuovo): il primo stato pubblicato da un'entita'
#   scenario appena registrata riflette la valutazione delle condizioni, non `enabled` - non va
#   piu' interpretato da handle_entity_state_change come un disable manuale (bug #2: scenari con
#   condizioni False al boot si autodisabilitavano permanentemente).
# - handle_entity_state_change: rimossa la entity.async_write_ha_state() dopo un cambio di
#   `enabled` (allineato al pattern gia' usato da people.py/delivery.py, che non la fanno) -
#   quella write rileggeva subito le condizioni reali e poteva riportare `enabled` a False nello
#   stesso tick (bug #3: la riabilitazione manuale da Developer Tools si autoannullava).
# - ScenarioRegistry._batch_cvars (nuovo) + scenario_is_on(): l'occupancy/ConditionVariables per
#   un batch refresh e' calcolata una volta sola per l'intero giro invece che per ogni scenario
#   (bug medio: determine_occupancy() richiamato N volte invece di 1 per refresh).
# Backup: nessuno necessario, storia completa in git (branch locale, non ancora pushato upstream).
# Verificato con CI replica completa (ruff/mypy/pytest py3.13+3.14, 1185 test verdi, 96% coverage)
# e con nuovi test dedicati in tests/components/supernotify/test_native_entities_review_fixes.py.

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

    from .binary_sensor import SupernotifyScenarioBinarySensor
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
        # Populated by binary_sensor.py's async_setup_entry once the platform is loaded (after
        # initialize() below) - see register_entity/unregister_entity. Empty (and harmless to
        # look up against) before then, e.g. during initialize()'s own expose_entities() call
        # and in tests that build ScenarioRegistry directly without a config entry.
        self._entities: dict[str, SupernotifyScenarioBinarySensor] = {}
        # Scenario names whose binary_sensor has been registered but hasn't yet published its
        # own first state. Populated by register_entity(), consumed by
        # handle_entity_state_change() - see that method for why the first publish must be
        # told apart from a real manual toggle.
        self._pending_first_publish: set[str] = set()
        # Shared occupancy/ConditionVariables snapshot for the scenario currently being batch
        # refreshed - set for the duration of async_refresh_scenario_states()'s loop, read by
        # scenario_is_on() so determine_occupancy() runs once per refresh instead of once per
        # scenario. None outside of a batch refresh (each scenario_is_on() call then computes
        # its own, e.g. a single entity being read on demand).
        self._batch_cvars: ConditionVariables | None = None

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

    def register_entity(self, name: str, entity: SupernotifyScenarioBinarySensor) -> None:
        """Called by SupernotifyScenarioBinarySensor.async_added_to_hass()."""
        self._entities[name] = entity
        # Registering happens just before HA publishes this entity's first state (see
        # handle_entity_state_change) - mark it so that first publish isn't mistaken for a
        # manual toggle.
        self._pending_first_publish.add(name)

    def unregister_entity(self, name: str) -> None:
        """Called by SupernotifyScenarioBinarySensor.async_will_remove_from_hass()."""
        self._entities.pop(name, None)
        self._pending_first_publish.discard(name)

    def scenario_is_on(self, scenario: Scenario) -> bool | None:
        """`is_on` for SupernotifyScenarioBinarySensor - None maps to STATE_UNKNOWN."""
        state = self._scenario_state(scenario, self._batch_cvars)
        if state == STATE_UNKNOWN:
            return None
        return state == STATE_ON

    def handle_entity_state_change(self, entity_id: str, new_state: State) -> bool | None:
        """React to a scenario binary_sensor being toggled on/off.

        Returns None if entity_id isn't one of ours, True if it was recognised and its
        enabled state changed, False if recognised but unknown or already in that state.
        """
        prefix = f"binary_sensor.{DOMAIN}_scenario_"
        if not entity_id.startswith(prefix):
            return None

        name = entity_id.removeprefix(prefix)
        scenario = self.scenarios.get(name)
        if scenario is None:
            _LOGGER.warning("SUPERNOTIFY Event for unknown scenario %s", entity_id)
            return False
        if name in self._pending_first_publish:
            # A scenario's binary_sensor state reflects its *condition evaluation*, not
            # `enabled` (unlike delivery/recipient, where the published state IS the enabled
            # flag - see people.py/delivery.py's own handle_entity_state_change). So the very
            # first state this entity ever publishes, right after being added to hass, must
            # not be mistaken for someone having manually toggled it off - e.g. a "sera"
            # scenario evaluating False at boot, in daylight, is normal and not a disable.
            # Only that first publish is suppressed; every later state change is a real event.
            self._pending_first_publish.discard(name)
            _LOGGER.debug("SUPERNOTIFY Ignoring initial state publish for scenario %s", scenario.name)
            return False
        if new_state.state == STATE_OFF and scenario.enabled:
            scenario.enabled = False
            _LOGGER.info("SUPERNOTIFY Disabling scenario %s", scenario.name)
            return True
        if new_state.state == STATE_ON and not scenario.enabled:
            scenario.enabled = True
            _LOGGER.info("SUPERNOTIFY Enabling scenario %s", scenario.name)
            # Deliberately no entity.async_write_ha_state() here, unlike an earlier version of
            # this method (and unlike people.py/delivery.py, where it would be safe): a
            # scenario's is_on re-evaluates its conditions from scratch on every read (see
            # scenario_is_on/_scenario_state), which can still be False right now - e.g.
            # re-enabling a "sera" scenario in daylight. Writing immediately would read that
            # back, publish OFF, and the resulting state-change event would flip `enabled`
            # back off in the same tick, before the manual toggle was ever visible. Leaving the
            # entity alone here means the manually-set state holds until the next real refresh
            # (reactive condition-entity change or periodic sweep), same as before this was a
            # real Entity.
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
        """Ask each affected scenario's binary_sensor entity to re-read and re-publish its state.

        Triggered by the 1-minute timer (time/date scenarios and any dependency
        not captured by entity extraction) and by state changes of the scenarios'
        condition entities (immediate reactivity). The entity's own `is_on`
        property (via scenario_is_on() above) does the actual (pure, in-memory)
        evaluation on read; this only decides which entities need to refresh, and
        is a no-op for a scenario with no entity registered yet (e.g. before the
        binary_sensor platform has finished loading).
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

        # Computed once for the whole batch (see _batch_cvars/scenario_is_on) rather than once
        # per scenario below - determine_occupancy() is only dict lookups, not real I/O, but
        # doing it once per refresh instead of once per scenario is the correct scale for a
        # mechanism meant to run on every relevant state change and every periodic sweep.
        occupiers = self._people_registry.determine_occupancy()
        self._batch_cvars = ConditionVariables([], [], [], PRIORITY_MEDIUM, occupiers, None, None)
        try:
            for name in self.scenarios if names is None else names:
                entity = self._entities.get(name)
                if entity is not None:
                    entity.async_write_ha_state()
        finally:
            self._batch_cvars = None


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
