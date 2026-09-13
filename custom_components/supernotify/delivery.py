from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.group.const import DOMAIN as HA_GROUP_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
    CONF_ACTION,
    CONF_ALIAS,
    CONF_CONDITIONS,
    CONF_DEBUG,
    CONF_ENABLED,
    CONF_NAME,
    CONF_OPTIONS,
    CONF_TARGET,
    STATE_OFF,
    STATE_ON,
)

from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import ConditionVariables, DeliveryConfig, SelectionRule, Target

from . import DOMAIN
from .common import sanitize
from .const import (
    ATTR_ENABLED,
    ATTR_MOBILE_APP_ID,
    CONF_DATA,
    CONF_INCLUSION,
    CONF_LOAD,
    CONF_MESSAGE,
    CONF_OCCUPANCY,
    CONF_TARGET_REQUIRED,
    CONF_TARGET_USAGE,
    CONF_TEMPLATE,
    CONF_TITLE,
    CONF_TRANSPORT,
    INCLUSION_DEFAULT,
    INCLUSION_EXPLICIT,
    INCLUSION_FALLBACK,
    INCLUSION_FALLBACK_ON_ERROR,
    OPTION_DATA_KEYS_EXCLUDE_RE,
    OPTION_DATA_KEYS_INCLUDE_RE,
    OPTION_DATA_KEYS_SELECT,
    OPTION_DEVICE_AREA_SELECT,
    OPTION_DEVICE_DISCOVERY,
    OPTION_DEVICE_DOMAIN,
    OPTION_DEVICE_LABEL_SELECT,
    OPTION_DEVICE_MANUFACTURER_SELECT,
    OPTION_DEVICE_MODEL_SELECT,
    OPTION_DEVICE_OS_SELECT,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    OPTION_TARGET_PLATFORM_SELECT,
    OPTION_TARGET_SELECT,
    RESERVED_DELIVERY_NAMES,
    SELECT_EXCLUDE,
    SELECT_INCLUDE,
)

if TYPE_CHECKING:
    from homeassistant.core import State
    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.hass_api import DeviceInfo
    from custom_components.supernotify.transport import Transport

    from .context import Context
    from .schema import ConditionsFunc

_LOGGER = logging.getLogger(__name__)


class Delivery(DeliveryConfig):
    def __init__(self, name: str, conf: ConfigType, transport: Transport) -> None:
        conf = conf or {}
        self.name: str = name
        self.transport: Transport = transport
        self._raw_conf: ConfigType = conf
        transport_defaults: DeliveryConfig = self.transport.delivery_defaults
        super().__init__(conf, delivery_defaults=transport_defaults)
        self.enabled: bool = conf.get(CONF_ENABLED, self.transport.enabled)
        self.conditions: ConditionsFunc | None = None
        self.transport_data: dict[str, Any] = {}
        if self.options.get(OPTION_TARGET_SELECT):
            self.target_selector: SelectionRule | None = SelectionRule(self.options.get(OPTION_TARGET_SELECT))
        else:
            self.target_selector = None
        if self.options.get(OPTION_TARGET_PLATFORM_SELECT):
            self.platform_selector: SelectionRule | None = SelectionRule(self.options.get(OPTION_TARGET_PLATFORM_SELECT))
        else:
            self.platform_selector = None
        self.upgrade_deprecations(conf)

    async def initialize(self, context: Context) -> bool:
        errors = 0
        if CONF_INCLUSION not in self._raw_conf and INCLUSION_DEFAULT not in self.inclusion:
            _LOGGER.warning(
                "SUPERNOTIFY Delivery %s has no explicit inclusion, but transport %s no longer defaults to "
                "'default' - it will not fire implicitly",
                self.name,
                self.transport.name,
            )
            context.hass_api.raise_issue(
                f"delivery_{self.name}_lost_implicit_inclusion",
                issue_key="delivery_lost_implicit_inclusion",
                issue_map={"delivery": self.name, "transport": self.transport.name},
                learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
            )
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

        self.discover_devices(context)
        self.transport_data = self.transport.setup_delivery_options(self.options, self.name)
        return errors == 0

    def upgrade_deprecations(self, conf: ConfigType) -> None:
        # v1.9.0
        if (
            OPTION_DATA_KEYS_INCLUDE_RE in self.options or OPTION_DATA_KEYS_EXCLUDE_RE in self.options
        ) and not self.options.get(OPTION_DATA_KEYS_SELECT):
            _LOGGER.warning(
                "SUPERNOTIFY Deprecated use of data_keys_include_re/data_keys_exclude_re options - use data_keys_select"
            )
            self.options[OPTION_DATA_KEYS_SELECT] = {
                SELECT_INCLUDE: self.options.get(OPTION_DATA_KEYS_INCLUDE_RE),
                SELECT_EXCLUDE: self.options.get(OPTION_DATA_KEYS_EXCLUDE_RE),
            }
        # v1.9.0
        if OPTION_TARGET_INCLUDE_RE in self.options and not self.options.get(OPTION_TARGET_SELECT):
            _LOGGER.warning("SUPERNOTIFY Deprecated use of target_include_re option - use target_select")
            self.options[OPTION_TARGET_SELECT] = {SELECT_INCLUDE: self.options.get(OPTION_TARGET_INCLUDE_RE)}

    def discover_devices(self, context: Context) -> None:
        if self.options.get(OPTION_DEVICE_DISCOVERY, False):
            for domain in self.options.get(OPTION_DEVICE_DOMAIN, []):
                discovered: int = 0
                added: int = 0
                for d in context.hass_api.discover_devices(
                    domain,
                    device_model_select=SelectionRule(self.options.get(OPTION_DEVICE_MODEL_SELECT)),
                    device_manufacturer_select=SelectionRule(self.options.get(OPTION_DEVICE_MANUFACTURER_SELECT)),
                    device_os_select=SelectionRule(self.options.get(OPTION_DEVICE_OS_SELECT)),
                    device_area_select=SelectionRule(self.options.get(OPTION_DEVICE_AREA_SELECT)),
                    device_label_select=SelectionRule(self.options.get(OPTION_DEVICE_LABEL_SELECT)),
                ):
                    discovered += 1
                    if self.target is None:
                        self.target = Target()
                    if domain == "mobile_app":
                        mobile_app: DeviceInfo | None = context.hass_api.mobile_app_by_device_id(d.device_id)
                        if mobile_app and mobile_app.action:
                            mobile_app_id = mobile_app.mobile_app_id if mobile_app else None
                            if mobile_app_id and mobile_app_id not in self.target.mobile_app_ids:
                                _LOGGER.debug(
                                    f"SUPERNOTIFY Found mobile {d.model} device {d.device_name} for {domain}, id {d.device_id}"
                                )
                                self.target.extend(ATTR_MOBILE_APP_ID, mobile_app_id)
                                added += 1
                        else:
                            _LOGGER.debug(f"SUPERNOTIFY Skipped mobile without notify entity {d.device_name}, id {d.device_id}")
                    else:
                        if d.device_id not in self.target.device_ids:
                            _LOGGER.debug(f"SUPERNOTIFY Found {d.model} device {d.device_name} for {domain}, id {d.device_id}")
                            self.target.extend(ATTR_DEVICE_ID, d.device_id)
                            added += 1

                _LOGGER.info(f"SUPERNOTIFY {self.name} Device discovery for {domain} found {discovered} devices, added {added}")

    def select_targets(self, target: Target, hass_api: HomeAssistantAPI | None = None) -> Target:
        def selected(category: str, targets: list[str]) -> list[str]:
            if OPTION_TARGET_CATEGORIES in self.options and category not in self.options[OPTION_TARGET_CATEGORIES]:
                return []
            if self.target_selector and self.platform_selector and hass_api:
                # a target must satisfy both - except an HA group, which is exempted from
                # the platform check entirely: group membership/expansion isn't handled
                # here yet (only chime.py does that), and a group's registry platform is
                # unreliable anyway (YAML-defined vs UI-defined groups differ)
                return [
                    t
                    for t in targets
                    if t.split(".", 1)[0] == HA_GROUP_DOMAIN
                    or (self.target_selector.match(t) and self.platform_selector.match(hass_api.platform_for_entity(t)))
                ]
            if self.target_selector:
                targets = [t for t in targets if self.target_selector.match(t)]
            if self.platform_selector and hass_api:
                targets = [t for t in targets if self.platform_selector.match(hass_api.platform_for_entity(t))]
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

    def option(self, option_name: str, default: str | bool) -> str | bool:
        """Get an option value from delivery config or transport default options"""
        opt: str | bool | None = None
        if option_name in self.options:
            opt = self.options[option_name]
        if opt is None:
            _LOGGER.debug(
                "SUPERNOTIFY No default in delivery %s for option %s, setting to default %s", self.name, option_name, default
            )
            opt = default
        return opt

    def option_bool(self, option_name: str, default: bool = False) -> bool:
        return bool(self.option(option_name, default=default))

    def option_str(self, option_name: str) -> str:
        return str(self.option(option_name, default=""))

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
            CONF_INCLUSION: self.inclusion,
            CONF_TARGET: self.target,
            CONF_TARGET_REQUIRED: self.target_required,
            CONF_TARGET_USAGE: self.target_usage,
            CONF_DATA: self.data,
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

    async def initialize(self, context: Context) -> None:
        await self.initialize_transports(context)
        await self.autogenerate_deliveries(context)
        self.initialize_deliveries()

    def expose_entities(self, hass_api: HomeAssistantAPI) -> None:
        for transport in self.transports.values():
            # only expose a switch for a transport that's actually usable: either it has an
            # explicitly configured delivery, or it can auto-configure one - checked directly
            # (not via transport.enabled or self._deliveries) so a transport with real
            # prerequisites still gets a switch even while toggled off in config
            has_explicit_delivery = any(dc.get(CONF_TRANSPORT) == transport.name for dc in self._config_deliveries.values())
            if not has_explicit_delivery and transport.auto_configure(hass_api) is None:
                continue
            hass_api.expose_entity(
                f"transport_{transport.name}",
                state=STATE_ON if transport.enabled else STATE_OFF,
                attributes=sanitize(transport.attributes()),
                original_name=f"{transport.name} Transport Adaptor",
                original_icon="mdi:truck-fast",
            )
        for delivery in self._deliveries.values():
            hass_api.expose_entity(
                f"delivery_{delivery.name}",
                state=STATE_ON if delivery.enabled else STATE_OFF,
                attributes=sanitize(delivery.attributes()),
                original_name=f"{delivery.name} Delivery Configuration",
                original_icon="mdi:package-variant",
            )

    def handle_entity_state_change(self, entity_id: str, new_state: State) -> bool | None:
        """React to a delivery or transport binary_sensor being toggled on/off.

        Returns None if entity_id belongs to neither (not a delivery/transport entity of
        ours), True if it was recognised and its enabled state changed, False if recognised
        but unknown or already in that state.
        """
        delivery_prefix = f"binary_sensor.{DOMAIN}_delivery_"
        transport_prefix = f"binary_sensor.{DOMAIN}_transport_"
        if entity_id.startswith(delivery_prefix):
            delivery_name = entity_id.removeprefix(delivery_prefix)
            if new_state.state == STATE_OFF:
                return self.disable(delivery_name)
            if new_state.state == STATE_ON:
                return self.enable(delivery_name)
            _LOGGER.info("SUPERNOTIFY No change to delivery %s for state %s", delivery_name, new_state.state)
            return False

        if entity_id.startswith(transport_prefix):
            transport_name = entity_id.removeprefix(transport_prefix)
            transport = self.transports.get(transport_name)
            if transport is None:
                _LOGGER.warning("SUPERNOTIFY Event for unknown transport %s", entity_id)
                return False
            if new_state.state == STATE_OFF and transport.enabled:
                transport.enabled = False
                _LOGGER.info("SUPERNOTIFY Disabling transport %s", transport.name)
                return True
            if new_state.state == STATE_ON and not transport.enabled:
                transport.enabled = True
                _LOGGER.info("SUPERNOTIFY Enabling transport %s", transport.name)
                return True
            _LOGGER.info("SUPERNOTIFY No change to transport %s, already %s", transport.name, new_state)
            return False

        return None

    def initialize_deliveries(self) -> None:
        for delivery in self._deliveries.values():
            if delivery.enabled:
                if INCLUSION_FALLBACK_ON_ERROR in delivery.inclusion:
                    self._fallback_on_error.append(delivery)
                if INCLUSION_FALLBACK in delivery.inclusion:
                    self._fallback_by_default.append(delivery)
                if INCLUSION_DEFAULT in delivery.inclusion:
                    self._implicit_deliveries.append(delivery)
                # delivery.inclusion can also be INCLUSION_BY_SCENARIO
                # or INCLUSION_EXPLICIT to have it only used where asked for
                # default is INCLUSION_DEFAULT so every delivery used implicitly

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

    def resolve_name(self, name: str) -> str:
        """Backward compatibility for the original 'DEFAULT_x' auto-configured naming,
        long since replaced by plain transport names: a reference to the old 'DEFAULT_x'
        form resolves to the current 'x' delivery, if that's what actually exists now."""
        if name not in self._deliveries and name.startswith("DEFAULT_"):
            plain_name = name.removeprefix("DEFAULT_")
            if plain_name in self._deliveries:
                return plain_name
        return name

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
        """Deliveries switched on all the time via implicit inclusion"""
        return [d for d in self._implicit_deliveries if d.enabled]

    async def initialize_transports(self, context: Context) -> None:
        """Use configure_for_tests() to set transports to mocks or manually created fixtures"""
        if self._transport_instances:
            for transport in self._transport_instances:
                self.transports[transport.name] = transport
                await transport.initialize()
                await self.initialize_transport_deliveries(context, transport)
        if self._transport_types:
            for transport_class, kwargs in self._transport_types.items():
                transport_config: ConfigType = self._transport_configs.get(transport_class.name, {})
                if not transport_config.get(CONF_LOAD, True):
                    # not just disabled: excluded entirely, so no deliveries or entities either
                    continue
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
        _LOGGER.info("SUPERNOTIFY Configured deliveries %s", "; ".join(self._deliveries.keys()))

    async def initialize_transport_deliveries(self, context: Context, transport: Transport) -> None:
        """Validate and initialize deliveries at startup for this transport"""
        validated_deliveries: dict[str, Delivery] = {}
        deliveries_for_this_transport = {
            d: dc for d, dc in self._config_deliveries.items() if dc.get(CONF_TRANSPORT) == transport.name
        }
        for d, dc in deliveries_for_this_transport.items():
            if d == transport.name:
                # an explicit delivery literally named after its own transport is
                # validated later, in autogenerate_deliveries, once discovery has updated
                # transport.delivery_defaults - validating it against the stale
                # pre-discovery defaults here could reject it needlessly
                continue
            # don't care about ENABLED here since disabled deliveries can be overridden later
            delivery = Delivery(d, dc, transport)
            if not await delivery.initialize(context):
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

    async def autogenerate_deliveries(self, context: Context) -> None:
        # Every loaded, viable transport gets an auto-configured delivery, whether or not
        # explicit deliveries also exist for it - so supernotify can at least handle
        # notifications sensibly out of the box even with an otherwise empty config

        autogenerated: dict[str, Delivery] = {}
        for transport in self.transports.values():
            # auto-configure regardless of any explicit delivery already configured for this
            # transport - the two coexist, only a direct name collision (below) is skipped
            transport_definition: DeliveryConfig | None = transport.auto_configure(context.hass_api)

            # every transport is available as a delivery of the same name - no
            # 'DEFAULT_x' prefix (that's legacy naming, see resolve_name())
            generated_name = transport.name
            own_named_config = self._config_deliveries.get(generated_name)
            is_own_transport_delivery = own_named_config is not None and own_named_config.get(CONF_TRANSPORT) == transport.name
            # non-None only once the transport itself confirms it's viable, so later checks
            # can rely on it being set rather than re-deriving "viable" as a separate bool
            viable_transport_definition = (
                transport_definition
                if transport_definition is not None and transport.validate_action(transport_definition.action)
                else None
            )
            existing_delivery = self._deliveries.get(generated_name)
            if existing_delivery is not None:
                if viable_transport_definition is None:
                    # this transport has nothing to auto-configure, so the delivery
                    # already using its name (for a different transport) keeps it
                    _LOGGER.warning(
                        "SUPERNOTIFY Skipping auto-configured delivery for %s, name %s already in use",
                        transport.name,
                        generated_name,
                    )
                    continue
                # a transport's name is reserved for its own delivery once that transport
                # can actually auto-configure one - a delivery for a *different* transport
                # can't also use the name, unlike above where there was nothing to reserve it for
                _LOGGER.warning(
                    "SUPERNOTIFY Delivery %s is configured for transport %s, but %s is a reserved transport name "
                    "now that %s can auto-configure - dropping delivery %s in favour of the auto-configured one",
                    generated_name,
                    existing_delivery.transport.name,
                    generated_name,
                    transport.name,
                    generated_name,
                )
                context.hass_api.raise_issue(
                    f"delivery_{generated_name}_reserved_name",
                    issue_key="delivery_reserved_name",
                    issue_map={"delivery": generated_name},
                    learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
                )
                del self._deliveries[generated_name]

            if is_own_transport_delivery and own_named_config is not None:
                # an explicit delivery literally named after its own transport doesn't
                # need its own connection details - it's merged with (and overrides) the
                # auto-configured/discovered defaults, now that transport.delivery_defaults
                # has just been updated above, rather than being skipped in favour of a
                # separate same-named delivery. Delivery.initialize() below is the
                # authoritative validity check, independent of transport_definition.
                merged_delivery = Delivery(generated_name, own_named_config, transport)
                if await merged_delivery.initialize(context):
                    autogenerated[merged_delivery.name] = merged_delivery
                    _LOGGER.info(
                        "SUPERNOTIFY Merged auto-configured defaults into explicit delivery %s for %s",
                        generated_name,
                        transport.name,
                    )
                else:
                    _LOGGER.error(f"SUPERNOTIFY Ignoring delivery {generated_name} with errors")
                continue

            if viable_transport_definition is None:
                if transport_definition:
                    _LOGGER.debug(
                        "SUPERNOTIFY No auto-configured delivery for transport %s, action failed validation", transport.name
                    )
                continue
            _LOGGER.debug(
                "SUPERNOTIFY Building auto-configured delivery for %s from transport %s",
                transport.name,
                viable_transport_definition,
            )

            # a *different*-named explicit delivery already covers implicit
            # inclusion for this transport - don't also fire this one on every
            # notification, just leave it addressable by transport name
            has_explicit_delivery = any(dc.get(CONF_TRANSPORT) == transport.name for dc in self._config_deliveries.values())
            if has_explicit_delivery and INCLUSION_DEFAULT in viable_transport_definition.inclusion:
                viable_transport_definition.inclusion = [
                    s for s in viable_transport_definition.inclusion if s != INCLUSION_DEFAULT
                ]
                if INCLUSION_EXPLICIT not in viable_transport_definition.inclusion:
                    viable_transport_definition.inclusion.append(INCLUSION_EXPLICIT)

            generated_delivery = Delivery(generated_name, viable_transport_definition.as_dict(), transport)
            await generated_delivery.initialize(context)
            generated_delivery.enabled = transport.enabled
            autogenerated[generated_delivery.name] = generated_delivery
            _LOGGER.info(
                "SUPERNOTIFY Auto-configuring delivery %s for %s from transport %s",
                generated_name,
                transport.name,
                viable_transport_definition,
            )
        if autogenerated:
            self._deliveries.update(autogenerated)
