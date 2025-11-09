import logging
from typing import Any

from homeassistant.const import (
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITION,
    CONF_DEFAULT,
    CONF_ENABLED,
    CONF_NAME,
    CONF_OPTIONS,
    CONF_TARGET,
)
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.transport import Transport

from . import (
    CONF_DATA,
    CONF_MESSAGE,
    CONF_OCCUPANCY,
    CONF_PRIORITY,
    CONF_SELECTION,
    CONF_TEMPLATE,
    CONF_TITLE,
    CONF_TRANSPORT,
    OCCUPANCY_ALL,
    RESERVED_DELIVERY_NAMES,
    SELECTION_DEFAULT,
    SELECTION_FALLBACK,
    SELECTION_FALLBACK_ON_ERROR,
)
from .context import Context
from .model import DeliveryConfig, TransportConfig

_LOGGER = logging.getLogger(__name__)


class Delivery(DeliveryConfig):
    def __init__(self, name: str, conf: ConfigType, transport: "Transport") -> None:
        self.name: str = name
        self.alias: str | None = conf.get(CONF_ALIAS)
        self.transport: Transport = transport
        transport_defaults: DeliveryConfig = self.transport.delivery_defaults
        super().__init__(conf, delivery_defaults=transport_defaults)
        self.template: str | None = conf.get(CONF_TEMPLATE)
        self.default: bool = conf.get(CONF_DEFAULT, False)
        self.message: str | None = conf.get(CONF_MESSAGE)
        self.title: str | None = conf.get(CONF_TITLE)
        self.enabled: bool = conf.get(CONF_ENABLED, True)
        self.occupancy: str = conf.get(CONF_OCCUPANCY, OCCUPANCY_ALL)
        self.condition: ConfigType | None = conf.get(CONF_CONDITION)

    async def validate(self, context: "Context") -> bool:
        errors = 0
        if self.name in RESERVED_DELIVERY_NAMES:
            _LOGGER.warning("SUPERNOTIFY Delivery uses reserved word %s", self.name)
            context.hass_api.raise_issue(
                f"delivery_{self.name}_reserved_name",
                issue_key="delivery_reserved_name",
                issue_map={"delivery": self.name},
            )
            errors += 1
        if not self.transport.validate_action(self.action):
            _LOGGER.warning("SUPERNOTIFY Invalid action definition for delivery %s (%s)", self.name, self.action)
            context.hass_api.raise_issue(
                f"delivery_{self.name}_invalid_action",
                issue_key="delivery_invalid_action",
                issue_map={"delivery": self.name, "action": self.action or ""},
            )
            errors += 1

        if self.condition:
            try:
                await context.hass_api.evaluate_condition(self.condition, validate=True, strict=True)
                passed = True
                exception = ""
            except Exception as e:
                passed = False
                exception = str(e)
            if not passed:
                _LOGGER.warning("SUPERNOTIFY Invalid delivery condition for %s: %s", self.name, self.condition)
                context.hass_api.raise_issue(
                    f"delivery_{self.name}_invalid_condition",
                    issue_key="delivery_invalid_condition",
                    issue_map={"delivery": self.name, "condition": str(self.condition), "exception": exception},
                )
                errors += 1
        return errors == 0

    def option(self, option_name: str) -> str | bool:
        """Get an option value from delivery config or transport default options"""
        opt: str | bool | None = None
        if option_name in self.options:
            opt = self.options[option_name]
        if opt is None:
            _LOGGER.debug("SUPERNOTIFY No default in %s for option %s, setting to empty string", self.name, option_name)
            opt = ""
        return opt

    def option_bool(self, option_name: str) -> bool:
        return bool(self.option(option_name))

    def option_str(self, option_name: str) -> str:
        return str(self.option(option_name))

    def as_dict(self) -> dict[str, Any]:
        return {
            CONF_NAME: self.name,
            CONF_ALIAS: self.alias,
            CONF_TRANSPORT: self.transport.transport,
            CONF_TEMPLATE: self.template,
            CONF_DEFAULT: self.default,
            CONF_MESSAGE: self.message,
            CONF_TITLE: self.title,
            CONF_ENABLED: self.enabled,
            CONF_OCCUPANCY: self.occupancy,
            CONF_CONDITION: self.condition,
            CONF_TARGET: self.target.as_dict() if self.target else None,
            CONF_ACTION: self.action,
            CONF_OPTIONS: self.options,
            CONF_DATA: self.data,
            CONF_SELECTION: self.selection,
            CONF_PRIORITY: self.priority,
        }


class DeliveryRegistry:
    def __init__(
        self,
        deliveries: ConfigType | None = None,
        transport_configs: ConfigType | None = None,
        transport_types: list[type[Transport]] | None = None,
        transport_instances: list[Transport] | None = None,  # for unit tests only
    ) -> None:
        # raw configured deliveries
        self._deliveries: ConfigType = deliveries if isinstance(deliveries, dict) else {}
        # validated deliveries
        self.deliveries: dict[str, Delivery] = {}
        self.transports: dict[str, Transport] = {}
        self._transport_configs: dict[str, TransportConfig] = (
            {n: TransportConfig(n, c) for n, c in transport_configs.items()} if transport_configs else {}
        )

        self._fallback_on_error: list[Delivery] = []
        self._fallback_by_default: list[Delivery] = []
        self._default_deliveries: list[Delivery] = []
        self.default_delivery_by_transport: dict[str, Delivery] = {}
        self._transport_types: list[type[Transport]] = transport_types or []
        # test harness support
        self._transport_instances: list[Transport] | None = transport_instances

    async def initialize(self, context: "Context") -> None:
        await self.initialize_transports(context)
        self.initialize_deliveries()

    def initialize_deliveries(self) -> None:
        for delivery in self.deliveries.values():
            if delivery.enabled:
                if SELECTION_FALLBACK_ON_ERROR in delivery.selection:
                    self._fallback_on_error.append(delivery)
                if SELECTION_FALLBACK in delivery.selection:
                    self._fallback_by_default.append(delivery)
                if SELECTION_DEFAULT in delivery.selection:
                    self._default_deliveries.append(delivery)

    def delivery_config(self, delivery_name: str, transport_name: str) -> Delivery:
        try:
            return self.deliveries.get(delivery_name) or self.default_delivery_by_transport[transport_name]
        except KeyError as e:
            raise ValueError(f"Missing transport {transport_name} in delivery register") from e

    @property
    def fallback_by_default_deliveries(self) -> list[Delivery]:
        return [d for d in self._fallback_by_default if d.enabled]

    @property
    def fallback_on_error_deliveries(self) -> list[Delivery]:
        return [d for d in self._fallback_on_error if d.enabled]

    @property
    def default_deliveries(self) -> list[Delivery]:
        """Deliveries switched on all the time for implicit selection"""
        return [d for d in self._default_deliveries if d.enabled]

    async def initialize_transports(self, context: "Context") -> None:
        """Use configure_for_tests() to set transports to mocks or manually created fixtures"""
        if self._transport_instances:
            for transport in self._transport_instances:
                self.transports[transport.transport] = transport
                await transport.initialize()
                await self.initialize_transport_deliveries(context, transport)
        if self._transport_types:
            for transport_class in self._transport_types:
                transport_config: TransportConfig = self._transport_configs.get(
                    transport_class.transport, TransportConfig(transport_class.transport, {})
                )
                transport = transport_class(
                    context,
                    delivery_defaults=transport_config.delivery_defaults,
                    enabled=transport_config.enabled,
                    device_domain=transport_config.device_domain,
                    device_discovery=transport_config.device_discovery,
                    target_required=transport_config.target_required,
                )
                self.transports[transport_class.transport] = transport
                await transport.initialize()
                await self.initialize_transport_deliveries(context, transport)
                self.transports[transport_class.transport] = transport

        unconfigured_deliveries = [dc for d, dc in self._deliveries.items() if d not in self.deliveries]
        for bad_del in unconfigured_deliveries:
            # presumably there was no transport for these
            context.hass_api.raise_issue(
                f"delivery_{bad_del.get(CONF_NAME)}_for_transport_{bad_del.get(CONF_TRANSPORT)}_failed_to_configure",
                issue_key="delivery_unknown_transport",
                issue_map={"delivery": bad_del.get(CONF_NAME), "transport": bad_del.get(CONF_TRANSPORT)},
            )
        _LOGGER.info("SUPERNOTIFY configured deliveries %s", "; ".join(self.deliveries.keys()))

    async def initialize_transport_deliveries(self, context: Context, transport: Transport) -> None:
        """Validate and initialize deliveries at startup for this transport"""
        validated_deliveries: dict[str, Delivery] = {}
        deliveries_for_this_transport = {
            d: dc for d, dc in self._deliveries.items() if dc.get(CONF_TRANSPORT) == transport.transport
        }
        for d, dc in deliveries_for_this_transport.items():
            # don't care about ENABLED here since disabled deliveries can be overridden later
            delivery = Delivery(d, dc, transport)
            if not await delivery.validate(context):
                _LOGGER.error(f"SUPERNOTIFY Ignoring delivery {d} with errors")
            else:
                validated_deliveries[d] = delivery
                if delivery.default:
                    if (
                        transport.transport not in self.default_delivery_by_transport
                        or self.default_delivery_by_transport[transport.transport].name == delivery.name
                    ):
                        # pick the first delivery with default flag set as the default
                        self.default_delivery_by_transport[transport.transport] = delivery
                    elif delivery.name != self.default_delivery_by_transport[transport.transport].name:
                        _LOGGER.debug("SUPERNOTIFY Multiple default deliveries, skipping %s", d)
                    else:
                        _LOGGER.warning("SUPERNOTIFY Unreachable code in default deliveries, skipping %s", d)

        if transport.transport not in self.default_delivery_by_transport:
            transport_definition: DeliveryConfig = transport.delivery_defaults
            if transport_definition:
                _LOGGER.info(
                    "SUPERNOTIFY Building default delivery for %s from transport %s", transport.transport, transport_definition
                )
                default_delivery = Delivery(f"DEFAULT_{transport.transport}", {}, transport)
                # validated_deliveries[default_delivery.name]=default_delivery
                self.default_delivery_by_transport[transport.transport] = default_delivery
            else:
                _LOGGER.debug("SUPERNOTIFY No default delivery or transport_definition for transport %s", transport.transport)

        self.deliveries.update(validated_deliveries)

        _LOGGER.debug(
            "SUPERNOTIFY Validated transport %s, default delivery %s, default action %s, valid deliveries: %s",
            transport.transport,
            self.default_delivery_by_transport[transport.transport],
            transport.delivery_defaults.action,
            [d for d in self.deliveries.values() if d.enabled and d.transport == transport],
        )
