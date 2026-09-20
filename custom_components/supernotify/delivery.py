from __future__ import annotations

import logging
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
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

from . import DOMAIN
from .common import ensure_list, sanitize
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
    INCLUSION_FALLBACK,
    INCLUSION_FALLBACK_ON_ERROR,
    RESERVED_DELIVERY_NAMES,
)
from .hass_api import HomeAssistantAPI
from .model import ConditionVariables, DeliveryConfig, EntityCategory, SelectionRule, Target
from .options import (
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
    OPTION_TARGET_SELECT,
    SELECT_EXCLUDE,
    SELECT_INCLUDE,
)
from .static_config import TRANSPORT_NAMES

if TYPE_CHECKING:
    from homeassistant.core import State
    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.hass_api import TrackedDeviceDetails
    from custom_components.supernotify.transport import Transport

    from .context import Context
    from .schema import ConditionsFunc

_LOGGER = logging.getLogger(__name__)


class DeliveryProvenance(StrEnum):
    DEFAULT_STANDARD = auto()
    EXTRA_STANDARD = auto()
    CONFIG = auto()


class Delivery(DeliveryConfig):
    def __init__(
        self, name: str, conf: ConfigType, transport: Transport, provenance: DeliveryProvenance = DeliveryProvenance.CONFIG
    ) -> None:
        conf = conf or {}
        self.name: str = name
        self.provenance: DeliveryProvenance = provenance
        self.transport: Transport = transport
        self._raw_conf: ConfigType = conf
        transport_defaults: DeliveryConfig = self.transport.delivery_defaults
        super().__init__(conf, delivery_defaults=transport_defaults)
        if isinstance(self.target, Target):
            # a value set directly on this delivery's own `target:` is exclusively scoped to
            # it - unlike a blended notification-level target list - so it's safe to claim an
            # unqualified value (no shape a validator recognises) for this transport. (The
            # isinstance check, not just a None check, is deliberate: a test double `Mock()`
            # transport can leave `self.target` as an auto-mocked attribute rather than None.)
            self.target = self.reclassify_unqualified_target(self.target)
        self.enabled: bool = conf.get(CONF_ENABLED, self.transport.enabled)
        self.conditions: ConditionsFunc | None = None
        self.transport_data: dict[str, Any] = {}
        if self.options.get(OPTION_TARGET_SELECT):
            self.target_selector: SelectionRule | None = SelectionRule(self.options.get(OPTION_TARGET_SELECT))
        else:
            self.target_selector = None
        self.upgrade_deprecations(conf)

    async def initialize(self, context: Context) -> bool:
        errors = 0
        if self.name in TRANSPORT_NAMES and self.transport.name != self.name:
            _LOGGER.warning(
                "SUPERNOTIFY Delivery %s is a reserved name for the standard delivery of %s transport", self.name, self.name
            )
            context.hass_api.raise_issue(
                f"delivery_{self.name}_reserved_name",
                issue_key="delivery_reserved_name",
                issue_map={"delivery": self.name},
                learn_more_url="https://supernotify.rhizomatics.org.uk/deliveries",
            )
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
                        mobile_app: TrackedDeviceDetails | None = context.hass_api.mobile_app_by_device_id(d.device_id)
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

    @property
    def target_categories(self) -> list[str | EntityCategory]:
        """The target categories this delivery accepts - the query point for "what does this

        delivery support", so callers never need to look at `Transport` and `OPTION_TARGET_
        CATEGORIES` separately. For every transport other than `generic`, this is direct
        delegation to `self.transport.target_categories` (a delivery rarely needs to widen
        what its transport understands). `generic` is the bring-your-own-categories
        transport - it declares nothing itself, so a delivery's own `OPTION_TARGET_CATEGORIES`
        (e.g. a made-up "slack_channel" category) is what actually defines its categories.

        The configured list is listed first, so it takes precedence as the reclassification
        fallback in `reclassify_unqualified_target()` when both are present.
        """
        configured = ensure_list(self.options.get(OPTION_TARGET_CATEGORIES))
        return [*configured, *self.transport.target_categories]

    def reclassify_unqualified_target(self, target: Target) -> Target:
        """Reclassify this delivery's uncategorised target values into its primary target

        category, since a value with no distinguishing shape (e.g. an MQTT topic, a Discord
        channel ID, or a made-up category for `generic`, like a Slack channel) would
        otherwise never survive `select_targets()` on its own. Left alone if this delivery's
        `target_categories` explicitly lists the uncategorised bucket itself - that's a
        deliberate choice to accept unqualified values exactly as they are - or if it has no
        plain-string category to fall back to at all.

        Only safe to call on a `Target` that is exclusively scoped to this one delivery - its
        own configured `target:`, or a per-delivery override - never on a blended,
        notification-level target list. There, an unqualified value must stay unclaimed
        rather than being guessed at: it could belong to a different delivery entirely, and
        claiming it here would leak it away from wherever it actually belongs.
        """
        unqualified = target.targets.get(Target.UNKNOWN_CUSTOM_CATEGORY)
        if not unqualified:
            return target
        declared = self.target_categories
        if Target.UNKNOWN_CUSTOM_CATEGORY in declared:
            return target
        primary = next((c for c in declared if isinstance(c, str)), None)
        if primary is None:
            # this target is exclusively scoped to this delivery (the safety precondition
            # above), so if there's genuinely nowhere for it to go, it's not a value meant
            # for a different delivery - it's just unmappable, and would otherwise be
            # dropped with no visible explanation
            _LOGGER.warning(
                "SUPERNOTIFY Delivery %s (%s) has no target category to accept unqualified target(s) %s - "
                "dropping. Known categories for this delivery: %s",
                self.name,
                self.transport.name,
                unqualified,
                [c if isinstance(c, str) else "entity_id" for c in declared] or "none",
            )
            return target
        result = target.safe_copy()
        result.targets.pop(Target.UNKNOWN_CUSTOM_CATEGORY, None)
        result.extend(primary, unqualified)
        return result

    def select_targets(self, target: Target, hass_api: HomeAssistantAPI | None = None) -> Target:
        declared_categories = self.target_categories
        plain_categories = {c for c in declared_categories if isinstance(c, str)}
        entity_selectors = [c for c in declared_categories if isinstance(c, EntityCategory)]

        def selected(category: str, targets: list[str]) -> list[str]:
            # a target category named after this delivery, or after its transport, is always
            # destined here. The two serve different purposes and both stay available:
            #  - the TRANSPORT name (`sms:value`) reaches every delivery of that transport, so
            #    scenario/time/occupancy selection logic can still decide which one actually
            #    fires - the same as it would for a plain, auto-matched value
            #  - a specific DELIVERY name (`shortcode_sms:value`) pins the target to just that
            #    one delivery, for when two deliveries of the same transport must stay distinct
            #    (e.g. `email` vs `html_email`)
            if category != self.name and category != self.transport.name:
                if entity_selectors and category == ATTR_ENTITY_ID:
                    targets = [
                        t
                        for t in targets
                        if any(
                            sel.matches(t, hass_api.platform_for_entity(t) if hass_api else None, check_platform=bool(hass_api))
                            for sel in entity_selectors
                        )
                    ]
                    if not targets:
                        return []
                elif plain_categories:
                    # this delivery declares fixed categories (from its transport, its own
                    # config, or both) - anything outside that set is rejected
                    if category not in plain_categories:
                        return []
                # else: this delivery declares no categories at all (e.g. `generic` with no
                # config) - nothing to restrict against
            if self.target_selector:
                targets = [t for t in targets if self.target_selector.match(t)]
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

        self._transport_types: dict[type[Transport], dict[str, Any]]
        if isinstance(transport_types, list):
            self._transport_types = {t: {} for t in transport_types}
        else:
            self._transport_types = transport_types or {}
        # test harness support
        self._transport_instances: list[Transport] | None = transport_instances

    async def initialize(self, context: Context) -> None:
        await self.initialize_transports(context)
        await self.initialize_deliveries()

    def unload_unused_transports(self) -> None:
        """Drop any transport that ended up with no delivery at all - explicit or auto-generated.

        Deliberately deferred until both initialize_transport_deliveries() (explicit) and
        build_standard_deliveries() (implicit) have run, rather than decided per-transport up
        front: whether a transport is worth having can only be known once the full, resolved
        set of deliveries exists - for a transport like `generic` (bring-your-own-action,
        entirely delivery-driven), there's no transport-level state to check in advance at all.
        """
        used_transport_names = {d.transport.name for d in self._deliveries.values()}
        for name in list(self.transports):
            if name not in used_transport_names:
                _LOGGER.info("SUPERNOTIFY %s transport has no deliveries, unloading", name)
                del self.transports[name]

    def expose_entities(self, hass_api: HomeAssistantAPI) -> None:
        for transport in self.transports.values():
            # unload_unused_transports() already removed anything with zero deliveries -
            # every transport still here has at least one, so it's worth a switch. Not
            # gated on transport.enabled - a disabled-but-usable transport still needs a
            # switch to re-enable it.
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

    async def initialize_deliveries(self) -> None:

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
        if self._transport_instances:
            """Used by configure_for_tests() and TestingContext to set transports to mocks or manually created fixtures"""
            for transport in self._transport_instances:
                self.transports[transport.name] = transport
                await transport.initialize()
                await self.initialize_transport_deliveries(context, transport)

        if self._transport_types:
            # production usage
            for transport_class, kwargs in self._transport_types.items():
                transport_config: ConfigType = self._transport_configs.get(transport_class.name, {})
                if not transport_config.get(CONF_LOAD, True):
                    # not just disabled: excluded entirely, so no deliveries or entities either
                    _LOGGER.debug("SUPERNOTIFY %s transport configured not to load", transport_class.name)
                    continue
                transport = transport_class(context, transport_config, **kwargs)
                if not transport.is_viable(context.hass_api):
                    _LOGGER.info("SUPERNOTIFY %s transport has no viable configuration, not loaded", transport_class.name)
                    continue
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

        self.unload_unused_transports()
        _LOGGER.info("SUPERNOTIFY Configured deliveries %s", "; ".join(self._deliveries.keys()))

    async def initialize_transport_deliveries(self, context: Context, transport: Transport) -> None:
        """Validate and initialize deliveries at startup for this transport"""
        validated_deliveries: dict[str, Delivery] = {}
        configured_deliveries: dict[str, ConfigType] = {
            d: dc for d, dc in self._config_deliveries.items() if dc.get(CONF_TRANSPORT) == transport.name
        }
        # hackily put here, since build_standard_deliveries can have side-effect of updating default deliveries
        standard_deliveries: dict[str, ConfigType] = transport.build_standard_deliveries(context.hass_api)

        for d, dc in configured_deliveries.items():
            # don't care about ENABLED here since disabled deliveries can be overridden later
            delivery = Delivery(d, dc, transport, DeliveryProvenance.CONFIG)
            if not await delivery.initialize(context):
                _LOGGER.error(f"SUPERNOTIFY Ignoring configured delivery {d} with errors")
            else:
                validated_deliveries[d] = delivery

        # merge in remaining standard deliveries but allow local override
        for d, dc in standard_deliveries.items():
            if d in configured_deliveries:
                _LOGGER.info("SUPERNOTIFY Default standard delivery %s overridden by config", d)
            else:
                provenance = DeliveryProvenance.DEFAULT_STANDARD if d == transport.name else DeliveryProvenance.EXTRA_STANDARD
                delivery = Delivery(d, dc, transport, provenance=provenance)

                if not await delivery.initialize(context):
                    _LOGGER.error(f"SUPERNOTIFY Ignoring standard delivery {d} with errors")
                else:
                    validated_deliveries[d] = delivery

        self._deliveries.update(validated_deliveries)

        _LOGGER.debug(
            "SUPERNOTIFY Validated transport %s, default action %s, valid deliveries: %s",
            transport.name,
            transport.delivery_defaults.action,
            [d for d in self._deliveries.values() if d.enabled and d.transport == transport],
        )
