"""Supernotify service, extending BaseNotificationService"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol
from homeassistant.const import (
    CONF_TARGET,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.loader import async_get_integration
from homeassistant.util.yaml import load_yaml_dict

from . import DOMAIN
from .archive import ARCHIVE_PURGE_MIN_INTERVAL
from .common import ensure_list
from .const import (
    ATTR_CUSTOM_TARGET,
    ATTR_DATA,
    ATTR_DELIVERY,
    ATTR_EXTRA_DATA,
    ATTR_MEDIA,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_SCENARIOS_APPLY,
    ATTR_SCENARIOS_CONSTRAIN,
    ATTR_SCENARIOS_REQUIRE,
    CONF_ACTION_GROUPS,
    CONF_ACTIONS,
    CONF_ARCHIVE,
    CONF_CAMERAS,
    CONF_DELIVERY,
    CONF_DUPE_CHECK,
    CONF_HOUSEKEEPING,
    CONF_LINKS,
    CONF_MEDIA_PATH,
    CONF_MESSAGE,
    CONF_MOBILE_DISCOVERY,
    CONF_RECIPIENTS,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SCENARIO_CONTROL,
    CONF_SCENARIOS,
    CONF_SNOOZE,
    CONF_TEMPLATE_PATH,
    CONF_TITLE,
    CONF_TRANSPORTS,
    OVERRIDE_KINDS,
)
from .engine import SupernotifyEngine
from .schema import ACTION_DATA_FIELDS, NOTIFY_ACTION_SCHEMA
from .target import Target

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


def lift_legacy_nested_data(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate a notify.supernotify-shaped payload sent to supernotify.notify.

    notify.supernotify carries Supernotify's own fields inside the call's `data:`, where
    supernotify.notify takes them at top level and keeps `data:` for the target service. Renaming
    the action on an old automation therefore leaves e.g. `message_html` and `priority` stranded
    in pass-through data. If the nested `data:` holds any Supernotify action field (including a
    further nested `data:`), treat it as the legacy block: lift Supernotify's fields to top level,
    keep the rest as pass-through.

    `extra_data`, the preferred home for pass-through data that legitimately reuses Supernotify
    field names (e.g. a mobile_app push's own `priority`), is never inspected or changed here.
    """
    data = dict(data)
    nested = data.get(ATTR_DATA)
    if isinstance(nested, dict) and not ACTION_DATA_FIELDS.isdisjoint(nested):
        _LOGGER.warning(
            "SUPERNOTIFY supernotify.notify has Supernotify fields (%s) inside `data:`, which looks like an automation "
            "changed from notify.supernotify. Treating as top-level fields, but move them out of `data:` to silence this, "
            "or use `extra_data:` if they are meant for the target service",
            ", ".join(sorted(ACTION_DATA_FIELDS.intersection(nested))),
        )
        lifted = {k: v for k, v in nested.items() if k in ACTION_DATA_FIELDS and k != ATTR_DATA}
        passthrough = {k: v for k, v in nested.items() if k not in ACTION_DATA_FIELDS}
        passthrough.update(nested.get(ATTR_DATA) or {})
        # explicit top-level values win, but the schema fills empty defaults (action_groups: [] etc)
        # for absent ones, so an empty top-level value must not shadow a lifted one
        data = lifted | {k: v for k, v in data.items() if k != ATTR_DATA and (v or k not in lifted)}
        if passthrough:
            data[ATTR_DATA] = passthrough
    return data


ACTION_NAMES: Final[tuple[str, ...]] = (
    "notify",
    "enquire_configuration",
    "enquire_implicit_deliveries",
    "enquire_deliveries_by_scenario",
    "enquire_last_notification",
    "enquire_active_scenarios",
    "enquire_scenarios",
    "enquire_occupancy",
    "enquire_recipients",
    "enquire_snoozes",
    "clear_snoozes",
    "purge_archive",
    "purge_media",
    "refresh_entities",
    "reset_overrides",
)

ATTR_KIND: Final[str] = "kind"
RESET_OVERRIDES_SCHEMA: Final = vol.Schema({vol.Optional(ATTR_KIND): vol.In(OVERRIDE_KINDS)})


@callback
def async_register_engine_actions(hass: HomeAssistant, engine: SupernotifyEngine, config: ConfigType) -> None:
    """Register the domain-scoped supplemental/debugging/admin services.

    Shared by the legacy YAML platform (async_get_service, below) and the config-entry setup
    (async_setup_entry in __init__.py), so both setup paths expose the same services. These
    are DOMAIN-scoped, not per config entry, so registration is guarded against being run
    twice - see ACTION_NAMES/async_unregister_engine_actions for the
    matching teardown.

    enquire_configuration closes over the raw config dict rather than `service`, because
    several of the fields it reports (delivery/transport/archive/dupe_check config, the full
    set of configured scenarios/recipients) are either private on the registries after
    initialize() or lossily reduced to derived values there - so `service` alone can't
    reconstruct them.
    """
    if hass.services.has_service(DOMAIN, "enquire_configuration"):
        return

    async def action_notify(call: ServiceCall) -> None:
        """supernotify.notify - an alternative to notify.supernotify with each option that would
        otherwise be buried in the generic `data:` field promoted to its own schema-checked,
        selector-driven field (see NOTIFY_ACTION_SCHEMA/services.yaml). Also propagates the
        calling action's Context through to deliveries, same as the SuperNotificationService override
        of _async_notify_message_service does for notify.supernotify/notify.<target>.
        """
        data = lift_legacy_nested_data(dict(call.data))
        # extra_data is what Notification knows as `data`, and wins over any same-named key in a legacy `data`
        if extra_data := data.pop(ATTR_EXTRA_DATA, None):
            data[ATTR_DATA] = {**(data.get(ATTR_DATA) or {}), **extra_data}
        message = data.pop(CONF_MESSAGE)
        title = data.pop(CONF_TITLE, None)
        target = data.pop(CONF_TARGET, None)
        # custom_target holds identifiers the target selector can't produce (e-mail addresses,
        # phone numbers, Slack ids etc) - merge into target here so nothing downstream needs to
        # know this field exists
        custom_target = ensure_list(data.pop(ATTR_CUSTOM_TARGET, None))
        if custom_target:
            if isinstance(target, dict):
                merged_target = dict(target)
                for category, values in Target(custom_target).targets.items():
                    merged_target[category] = [*ensure_list(merged_target.get(category)), *values]
                target = merged_target
            else:
                target = [*ensure_list(target), *custom_target]
        # camera_entity_id/clip_url/snapshot_url are promoted top-level fields for this action's
        # UI - fold them into media, overriding any same-named key already nested in media: itself
        promoted_media = {
            key: data.pop(key)
            for key in (ATTR_MEDIA_CAMERA_ENTITY_ID, ATTR_MEDIA_CLIP_URL, ATTR_MEDIA_SNAPSHOT_URL)
            if key in data
        }
        if promoted_media:
            media = dict(data.get(ATTR_MEDIA) or {})
            media.update(promoted_media)
            data[ATTR_MEDIA] = media
        await engine.async_send_message(message, title=title, target=target, data=data, context=call.context)

    def supplemental_action_enquire_configuration(_call: ServiceCall) -> dict[str, Any]:
        return {
            CONF_DELIVERY: config.get(CONF_DELIVERY, {}),
            CONF_LINKS: config.get(CONF_LINKS, ()),
            CONF_TEMPLATE_PATH: config.get(CONF_TEMPLATE_PATH, None),
            CONF_MEDIA_PATH: config.get(CONF_MEDIA_PATH, None),
            CONF_ARCHIVE: config.get(CONF_ARCHIVE, {}),
            CONF_MOBILE_DISCOVERY: config.get(CONF_MOBILE_DISCOVERY, ()),
            CONF_RECIPIENTS_DISCOVERY: config.get(CONF_RECIPIENTS_DISCOVERY, ()),
            CONF_RECIPIENTS: config.get(CONF_RECIPIENTS, ()),
            CONF_ACTIONS: config.get(CONF_ACTIONS, {}),
            CONF_HOUSEKEEPING: config.get(CONF_HOUSEKEEPING, {}),
            CONF_ACTION_GROUPS: config.get(CONF_ACTION_GROUPS, {}),
            CONF_SCENARIOS: list(config.get(CONF_SCENARIOS, {}).keys()),
            CONF_SCENARIO_CONTROL: config.get(CONF_SCENARIO_CONTROL, {}),
            CONF_TRANSPORTS: config.get(CONF_TRANSPORTS, {}),
            CONF_CAMERAS: config.get(CONF_CAMERAS, {}),
            CONF_DUPE_CHECK: config.get(CONF_DUPE_CHECK, {}),
            CONF_SNOOZE: config.get(CONF_SNOOZE, {}),
        }

    @callback
    def supplemental_action_refresh_entities(_call: ServiceCall) -> None:
        # a callback, so run in the event loop - it writes entity state
        engine.refresh_entities()

    @callback
    def supplemental_action_reset_overrides(call: ServiceCall) -> dict[str, Any]:
        # a callback, so run in the event loop - it writes entity state
        kind: str | None = call.data.get(ATTR_KIND)
        return {"reset": engine.reset_overrides((kind,) if kind else OVERRIDE_KINDS)}

    def supplemental_action_enquire_implicit_deliveries(_call: ServiceCall) -> dict[str, Any]:
        return engine.enquire_implicit_deliveries()

    def supplemental_action_enquire_deliveries_by_scenario(_call: ServiceCall) -> dict[str, Any]:
        return engine.enquire_deliveries_by_scenario()

    def supplemental_action_enquire_last_notification(call: ServiceCall) -> dict[str, Any]:
        diagnostics = call.data.get("diagnostics", False)
        return engine.last_notification.contents(diagnostics=diagnostics) if engine.last_notification else {}

    async def supplemental_action_enquire_active_scenarios(call: ServiceCall) -> dict[str, Any]:
        trace = call.data.get("trace", False)
        result: dict[str, Any] = {"scenarios": await engine.enquire_active_scenarios()}
        if trace:
            result["trace"] = await engine.trace_active_scenarios()
        return result

    def supplemental_action_enquire_scenarios(_call: ServiceCall) -> dict[str, Any]:
        return {"scenarios": engine.enquire_scenarios()}

    async def supplemental_action_enquire_occupancy(_call: ServiceCall) -> dict[str, Any]:
        return {"scenarios": await engine.enquire_occupancy()}

    def supplemental_action_enquire_snoozes(_call: ServiceCall) -> dict[str, Any]:
        return {"snoozes": engine.enquire_snoozes()}

    def supplemental_action_clear_snoozes(_call: ServiceCall) -> dict[str, Any]:
        return {"cleared": engine.clear_snoozes()}

    def supplemental_action_enquire_recipients(_call: ServiceCall) -> dict[str, Any]:
        return {"recipients": engine.enquire_recipients()}

    async def supplemental_action_purge_archive(call: ServiceCall) -> dict[str, Any]:
        days = call.data.get("days")
        if not engine.context.archive.enabled:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_archive_configured",
            )
        purged = await engine.context.archive.cleanup(days=days, force=True)
        arch_size = await engine.context.archive.size()
        return {
            "purged": purged,
            "remaining": arch_size,
            "interval": ARCHIVE_PURGE_MIN_INTERVAL,
            "days": engine.context.archive.archive_days if days is None else days,
        }

    async def supplemental_action_purge_media(call: ServiceCall) -> dict[str, Any]:
        days = call.data.get("days")
        if not engine.context.media_storage.media_path:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_media_storage_configured",
            )
        purged = await engine.context.media_storage.cleanup(days=days, force=True)
        size = await engine.context.media_storage.size()
        return {
            "purged": purged,
            "remaining": size,
            "interval": engine.context.media_storage.purge_minute_interval,
            "days": engine.context.media_storage.days if days is None else days,
        }

    hass.services.async_register(
        DOMAIN,
        "notify",
        action_notify,
        schema=NOTIFY_ACTION_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_configuration",
        supplemental_action_enquire_configuration,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_implicit_deliveries",
        supplemental_action_enquire_implicit_deliveries,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_deliveries_by_scenario",
        supplemental_action_enquire_deliveries_by_scenario,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_last_notification",
        supplemental_action_enquire_last_notification,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_active_scenarios",
        supplemental_action_enquire_active_scenarios,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_scenarios",
        supplemental_action_enquire_scenarios,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_occupancy",
        supplemental_action_enquire_occupancy,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_recipients",
        supplemental_action_enquire_recipients,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "enquire_snoozes",
        supplemental_action_enquire_snoozes,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "clear_snoozes",
        supplemental_action_clear_snoozes,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "purge_archive",
        supplemental_action_purge_archive,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "purge_media",
        supplemental_action_purge_media,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "refresh_entities",
        supplemental_action_refresh_entities,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        "reset_overrides",
        supplemental_action_reset_overrides,
        schema=RESET_OVERRIDES_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def async_describe_configured_names(hass: HomeAssistant, engine: SupernotifyEngine) -> None:
    """Show the deliveries and scenarios configured now in supernotify.notify's description.

    services.yaml can only hold a fixed description, so it's copied and set again with the scenario
    fields as dropdowns (still taking a typed name), and the configured delivery names as the
    delivery field's example - that field stays a free-form object, since it also takes a mapping.
    Names and descriptions still come from the translations, which are looked up by field.
    Called on every config entry setup, so a reload picks up changed names.
    """
    integration = await async_get_integration(hass, DOMAIN)
    services: dict[str, Any] = await hass.async_add_executor_job(load_yaml_dict, str(integration.file_path / "services.yaml"))
    notify: dict[str, Any] = services["notify"]
    fields: dict[str, Any] = notify["fields"]
    if deliveries := list(engine.context.delivery_registry.deliveries):
        fields[ATTR_DELIVERY]["example"] = f"[{', '.join(deliveries)}]"
    if scenarios := list(engine.context.scenario_registry.scenarios):
        for field in (ATTR_SCENARIOS_REQUIRE, ATTR_SCENARIOS_APPLY, ATTR_SCENARIOS_CONSTRAIN):
            fields["scenarios"]["fields"][field]["selector"] = {
                "select": {"options": scenarios, "multiple": True, "custom_value": True}
            }
    async_set_service_schema(hass, DOMAIN, "notify", notify)


@callback
def async_unregister_engine_actions(hass: HomeAssistant) -> None:
    """Undo async_register_engine_actions."""
    for name in ACTION_NAMES:
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)
