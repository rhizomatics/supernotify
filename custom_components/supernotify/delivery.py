import logging
import re
from typing import Any

from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_DEBUG,
    CONF_ENABLED,
    CONF_NAME,
    CONF_OPTIONS,
)
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import ConditionVariables, DeliveryConfig, Target
from custom_components.supernotify.transport import Transport

from . import (
    ATTR_ENABLED,
    CONF_MESSAGE,
    CONF_OCCUPANCY,
    CONF_SELECTION,
    CONF_TEMPLATE,
    CONF_TITLE,
    CONF_TRANSPORT,
    OCCUPANCY_ALL,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    RESERVED_DELIVERY_NAMES,
    SELECTION_DEFAULT,
    SELECTION_FALLBACK,
    SELECTION_FALLBACK_ON_ERROR,
    ConditionsFunc,
)
from .context import Context

_LOGGER = logging.getLogger(__name__)


class Delivery(DeliveryConfig):
    def __init__(self, name: str, conf: ConfigType, transport: "Transport") -> None:
        conf = conf or {}
        self.name: str = name
        self.alias: str | None = conf.get(CONF_ALIAS)
        self.transport: Transport = transport
        transport_defaults: DeliveryConfig = self.transport.delivery_defaults
        super().__init__(conf, delivery_defaults=transport_defaults)
        self.template: str | None = conf.get(CONF_TEMPLATE)
        self.message: str | None = conf.get(CONF_MESSAGE)
        self.title: str | None = conf.get(CONF_TITLE)
        self.enabled: bool = conf.get(CONF_ENABLED, self.transport.enabled)
        self.occupancy: str = conf.get(CONF_OCCUPANCY, OCCUPANCY_ALL)
        self.conditions_config: list[ConfigType] | None = conf.get(CONF_CONDITIONS)
        if not conf.get(CONF_CONDITIONS) and conf.get(CONF_CONDITION):
            self.conditions_config = conf.get(CONF_CONDITION)
        self.conditions: ConditionsFunc | None = None

    async def validate(self, context: "Context") -> bool:
        errors = 0
        if self.name in RESERVED_DELIVERY_NAMES:
            _LOGGER.warning("SUPERNOTIFY Delivery uses reserved word %s", self.name)
            context.hass_api.raise_issue(
                f"delivery_{self.name}_reserved_name",
                issue_key="delivery_reserved_name",
                issue_map={"delivery": self.name},
                learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
            )
            errors += 1
        if not self.transport.validate_action(self.action):
            _LOGGER.warning("SUPERNOTIFY Invalid action definition for delivery %s (%s)", self.name, self.action)
            context.hass_api.raise_issue(
                f"delivery_{self.name}_invalid_action",
                issue_key="delivery_invalid_action",
                issue_map={"delivery": self.name, "action": self.action or ""},
                learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
            )
            errors += 1

        if self.conditions_config:
            try:
                self.conditions = await context.hass_api.build_conditions(
                    self.conditions_config, validate=True, strict=True, name=self.name
                )
                passed = True
                exception = ""
            except Exception as e:
                passed = False
                exception = str(e)
            if not passed:
                _LOGGER.warning("SUPERNOTIFY Invalid delivery conditions for %s: %s", self.name, self.conditions_config)
                context.hass_api.raise_issue(
                    f"delivery_{self.name}_invalid_condition",
                    issue_key="delivery_invalid_condition",
                    issue_map={"delivery": self.name, "condition": str(self.conditions_config), "exception": exception},
                    learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
                )
                errors += 1
        return errors == 0

    def select_targets(self, target: Target) -> Target:
        def selected(category: str, targets: list[str]) -> list[str]:
            if OPTION_TARGET_CATEGORIES in self.options and category not in self.options[OPTION_TARGET_CATEGORIES]:
                return []
            if OPTION_TARGET_INCLUDE_RE in self.options:
                return [t for t in targets if any(re.fullmatch(r, t) for r in self.options[OPTION_TARGET_INCLUDE_RE])]
            return targets

        filtered_target = Target({k: selected(k, v) for k, v in target.targets.items()}, target_data=target.target_data)
        # TODO: in model class
        if target.target_specific_data:
            filtered_target.target_specific_data = {
                (c, t): data
                for (c, t), data in target.target_specific_data.items()
                if c in target.targets and t in target.targets[c]
            }
        return filtered_target

    def evaluate_conditions(self, condition_variables: ConditionVariables) -> bool | None:
        if not self.enabled:
            return False
        if self.conditions is None:
            return True
        # TODO: reconsider hass_api injection
        return self.transport.hass_api.evaluate_conditions(self.conditions, condition_variables)

    def option(self, option_name: str) -> str | bool:
        """Get an option value from delivery config or transport default options"""
        opt: str | bool | None = None
        if option_name in self.options:
            opt = self.options[option_name]
        if opt is None:
            _LOGGER.debug(
                "SUPERNOTIFY No default in delivery %s for option %s, setting to empty string", self.name, option_name
            )
            opt = ""
        return opt

    def option_bool(self, option_name: str) -> bool:
        return bool(self.option(option_name))

    def option_str(self, option_name: str) -> str:
        return str(self.option(option_name))

    def as_dict(self, **_kwargs: Any) -> dict[str, Any]:
        base = super().as_dict()
        base.update({
            CONF_NAME: self.name,
            CONF_ALIAS: self.alias,
            CONF_TRANSPORT: self.transport.name,
            CONF_TEMPLATE: self.template,
            CONF_MESSAGE: self.message,
            CONF_TITLE: self.title,
            CONF_ENABLED: self.enabled,
            CONF_OCCUPANCY: self.occupancy,
            CONF_CONDITIONS: self.conditions,
        })
        return base

    def attributes(self) -> dict[str, Any]:
        """For exposure as entity state"""
        attrs: dict[str, Any] = {
            ATTR_NAME: self.name,
            ATTR_ENABLED: self.enabled,
            CONF_TRANSPORT: self.transport.name,
            CONF_ACTION: self.action,
            CONF_OPTIONS: self.options,
            CONF_SELECTION: self.selection,
            CONF_DEBUG: self.debug,
        }
        if self.alias:
            attrs[ATTR_FRIENDLY_NAME] = self.alias
        return attrs


class DeliveryRegistry:
    def __init__(
        self,
        deliveries: ConfigType | None = None,
        transport_configs: ConfigType | None = None,
        transport_types: list[type[Transport]] | dict[type[Transport], dict[str, Any]] | None = None,
        # for unit tests only
        transport_instances: list[Transport] | None = None,
    ) -> None:
        # raw configured deliveries
        self._config_deliveries: ConfigType = deliveries if isinstance(deliveries, dict) else {}
        # validated deliveries
        self._deliveries: dict[str, Delivery] = {}
        self.transports: dict[str, Transport] = {}
        self._transport_configs: ConfigType = transport_configs or {}
        self._fallback_on_error: list[Delivery] = []
        self._fallback_by_default: list[Delivery] = []
        self._implicit_deliveries: list[Delivery] = []
        # test harness support
        self._transport_types: dict[type[Transport], dict[str, Any]]
        if isinstance(transport_types, list):
            self._transport_types = {t: {} for t in transport_types}
        else:
            self._transport_types = transport_types or {}
        self._transport_instances: list[Transport] | None = transport_instances

    async def initialize(self, context: "Context") -> None:
        await self.initialize_transports(context)
        self.autogenerate_deliveries(context.hass_api)
        self.initialize_deliveries()

    def initialize_deliveries(self) -> None:
        for delivery in self._deliveries.values():
            if delivery.enabled:
                if SELECTION_FALLBACK_ON_ERROR in delivery.selection:
                    self._fallback_on_error.append(delivery)
                if SELECTION_FALLBACK in delivery.selection:
                    self._fallback_by_default.append(delivery)
                if SELECTION_DEFAULT in delivery.selection:
                    self._implicit_deliveries.append(delivery)

    def enable(self, delivery_name: str) -> bool:
        delivery = self._deliveries.get(delivery_name)
        if delivery and not delivery.enabled:
            _LOGGER.info(f"SUPERNOTIFY Enabling delivery {delivery_name}")
            delivery.enabled = True
            return True
        return False

    def disable(self, delivery_name: str) -> bool:
        delivery = self._deliveries.get(delivery_name)
        if delivery and delivery.enabled:
            _LOGGER.info(f"SUPERNOTIFY Disabling delivery {delivery_name}")
            delivery.enabled = False
            return True
        return False

    @property
    def deliveries(self) -> dict[str, Delivery]:
        return dict(self._deliveries.items())

    @property
    def enabled_deliveries(self) -> dict[str, Delivery]:
        return {d: dconf for d, dconf in self._deliveries.items() if dconf.enabled}

    @property
    def disabled_deliveries(self) -> dict[str, Delivery]:
        return {d: dconf for d, dconf in self._deliveries.items() if not dconf.enabled}

    @property
    def fallback_by_default_deliveries(self) -> list[Delivery]:
        return [d for d in self._fallback_by_default if d.enabled]

    @property
    def fallback_on_error_deliveries(self) -> list[Delivery]:
        return [d for d in self._fallback_on_error if d.enabled]

    @property
    def implicit_deliveries(self) -> list[Delivery]:
        """Deliveries switched on all the time for implicit selection"""
        return [d for d in self._implicit_deliveries if d.enabled]

    async def initialize_transports(self, context: "Context") -> None:
        """Use configure_for_tests() to set transports to mocks or manually created fixtures"""
        if self._transport_instances:
            for transport in self._transport_instances:
                self.transports[transport.name] = transport
                await transport.initialize()
                await self.initialize_transport_deliveries(context, transport)
        if self._transport_types:
            for transport_class, kwargs in self._transport_types.items():
                transport_config: ConfigType = self._transport_configs.get(transport_class.name, {})
                transport = transport_class(context, transport_config, **kwargs)
                self.transports[transport_class.name] = transport
                await transport.initialize()
                await self.initialize_transport_deliveries(context, transport)
                self.transports[transport_class.name] = transport

        unconfigured_deliveries = [dc for d, dc in self._config_deliveries.items() if d not in self._deliveries]
        for bad_del in unconfigured_deliveries:
            # presumably there was no transport for these
            context.hass_api.raise_issue(
                f"delivery_{bad_del.get(CONF_NAME)}_for_transport_{bad_del.get(CONF_TRANSPORT)}_failed_to_configure",
                issue_key="delivery_unknown_transport",
                issue_map={"delivery": bad_del.get(CONF_NAME), "transport": bad_del.get(CONF_TRANSPORT)},
                learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
            )
        _LOGGER.info("SUPERNOTIFY configured deliveries %s", "; ".join(self._deliveries.keys()))

    async def initialize_transport_deliveries(self, context: Context, transport: Transport) -> None:
        """Validate and initialize deliveries at startup for this transport"""
        validated_deliveries: dict[str, Delivery] = {}
        deliveries_for_this_transport = {
            d: dc for d, dc in self._config_deliveries.items() if dc.get(CONF_TRANSPORT) == transport.name
        }
        for d, dc in deliveries_for_this_transport.items():
            # don't care about ENABLED here since disabled deliveries can be overridden later
            delivery = Delivery(d, dc, transport)
            if not await delivery.validate(context):
                _LOGGER.error(f"SUPERNOTIFY Ignoring delivery {d} with errors")
            else:
                validated_deliveries[d] = delivery

        self._deliveries.update(validated_deliveries)

        _LOGGER.debug(
            "SUPERNOTIFY Validated transport %s, default action %s, valid deliveries: %s",
            transport.name,
            transport.delivery_defaults.action,
            [d for d in self._deliveries.values() if d.enabled and d.transport == transport],
        )

    def autogenerate_deliveries(self, hass_api: HomeAssistantAPI) -> None:
        # If the config has no deliveries, check if a default delivery should be auto-generated
        # where there is a empty config, supernotify can at least handle NotifyEntities sensibly

        autogenerated: dict[str, Delivery] = {}
        for transport in [t for t in self.transports.values() if t.enabled]:
            if any(dc for dc in self._config_deliveries.values() if dc.get(CONF_TRANSPORT) == transport.name):
                # don't auto-configure if there's an explicit delivery configured for this transport
                continue

            transport_definition: DeliveryConfig | None = transport.auto_configure(hass_api)
            if transport_definition:
                _LOGGER.debug(
                    "SUPERNOTIFY Building default delivery for %s from transport %s", transport.name, transport_definition
                )
                # belt and braces transport checking its own discovery
                if transport.validate_action(transport_definition.action):
                    # auto generate a delivery that will be implicitly selected
                    default_delivery = Delivery(f"DEFAULT_{transport.name}", transport_definition.as_dict(), transport)
                    default_delivery.enabled = transport.enabled
                    autogenerated[default_delivery.name] = default_delivery
                    _LOGGER.info(
                        "SUPERNOTIFY Auto-generating a default delivery for %s from transport %s",
                        transport.name,
                        transport_definition,
                    )
                else:
                    _LOGGER.debug("SUPERNOTIFY No default delivery or transport_definition for transport %s", transport.name)
        if autogenerated:
            self._deliveries.update(autogenerated)
