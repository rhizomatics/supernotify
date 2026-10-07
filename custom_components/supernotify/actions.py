"""Supernotify service, extending BaseNotificationService"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from functools import partial
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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.template import Template
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import load_yaml_dict

from . import DOMAIN
from .archive import ARCHIVE_PURGE_MIN_INTERVAL, summarize_by_day, summarize_notification
from .common import ensure_list
from .const import (
    ATTR_CUSTOM_TARGET,
    ATTR_DATA,
    ATTR_DELIVERY,
    ATTR_DELIVERY_CONTROL,
    ATTR_DELIVERY_SELECTION,
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
    DELIVERY_SELECTION_EXPLICIT,
    OVERRIDE_KINDS,
)
from .engine import SupernotifyEngine
from .model import CommandType, QualifiedTargetType, RecipientType
from .schema import ACTION_DATA_FIELDS, NOTIFY_ACTION_SCHEMA
from .snoozer import SNOOZE_SCOPES, snooze_name_error
from .target import Target

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType
    from homeassistant.util.json import JsonObjectType

_LOGGER = logging.getLogger(__name__)

# what the schema fills in for fields a supernotify.notify call left out
_NOTIFY_ACTION_DEFAULTS: dict[str, Any] = NOTIFY_ACTION_SCHEMA({})


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
        # explicit top-level values win, but the schema fills defaults (action_groups: [], dry_run: live etc)
        # for absent ones, so an empty or default top-level value must not shadow a lifted one
        data = lifted | {
            k: v for k, v in data.items() if k != ATTR_DATA and (k not in lifted or (v and v != _NOTIFY_ACTION_DEFAULTS.get(k)))
        }
        if passthrough:
            data[ATTR_DATA] = passthrough
    return data


def merge_delivery_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Fold supernotify.notify's delivery dropdown and free-form Delivery Control into one `delivery`,
    written as it could have been in YAML.

    Names alone stay a list, restricting to those deliveries. Once Delivery Control has a mapping, the
    two become one mapping, and a delivery in both takes the form it has in Delivery Control. A mapping
    on its own only tunes deliveries without restricting them, so when names were also picked from the
    dropdown - which the UI pre-fills with the implicit deliveries, to add to or take from - the
    selection is made explicit, unless the call set it, keeping the dropdown's meaning of "only these".
    """
    data = dict(data)
    control: Any = data.pop(ATTR_DELIVERY_CONTROL, None)
    picked: Any = data.get(ATTR_DELIVERY)
    if not control:
        return data
    if not picked:
        data[ATTR_DELIVERY] = control
        return data
    if isinstance(control, dict) or isinstance(picked, dict):
        merged: dict[str, Any] = dict(picked) if isinstance(picked, dict) else dict.fromkeys(ensure_list(picked))
        merged.update(control if isinstance(control, dict) else dict.fromkeys(ensure_list(control)))
        data[ATTR_DELIVERY] = merged
        if not isinstance(picked, dict):
            data.setdefault(ATTR_DELIVERY_SELECTION, DELIVERY_SELECTION_EXPLICIT)
    else:
        data[ATTR_DELIVERY] = list(dict.fromkeys([*ensure_list(picked), *ensure_list(control)]))
    return data


VERBOSITY_SUMMARY: Final[str] = "summary"
VERBOSITY_STANDARD: Final[str] = "standard"
VERBOSITY_FULL: Final[str] = "full"
# counts per local day instead of the notifications themselves, and so without a default limit
VERBOSITY_DAILY: Final[str] = "daily"

# time periods ending now, as offered by the Home Assistant Activity view
ARCHIVE_PERIODS: Final[dict[str, dt.timedelta]] = {
    "last_hour": dt.timedelta(hours=1),
    "last_12_hours": dt.timedelta(hours=12),
    "last_day": dt.timedelta(days=1),
    "last_week": dt.timedelta(weeks=1),
    "last_month": dt.timedelta(days=30),
}

# only the fields with a fixed choice of values are checked, the rest are as loose as they were
ENQUIRE_ARCHIVE_SCHEMA: Final[vol.Schema] = vol.Schema(
    {
        vol.Optional("period"): vol.In(ARCHIVE_PERIODS),
        vol.Optional("verbosity"): vol.In((VERBOSITY_SUMMARY, VERBOSITY_STANDARD, VERBOSITY_FULL, VERBOSITY_DAILY)),
    },
    extra=vol.ALLOW_EXTRA,
)

ACTION_NAMES: Final[tuple[str, ...]] = (
    "notify",
    "enquire_archive",
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
    "snooze",
    "silence",
    "unsnooze",
    "purge_archive",
    "purge_media",
    "refresh_entities",
    "reset_overrides",
)

SNOOZE_MAX_MINUTES: Final[int] = 7 * 24 * 60
SNOOZE_REASON: Final[str] = "Action"
# what to snooze, silence or unsnooze, the same for all three actions
SNOOZE_TARGET_FIELDS: Final[dict[vol.Marker, Any]] = {
    vol.Optional("scope", default="everything"): vol.In(SNOOZE_SCOPES),
    vol.Optional("name"): cv.string,
    vol.Optional("person"): cv.entity_domain("person"),
}
# supernotify.snooze, supernotify.silence and supernotify.unsnooze: the command of a mobile action,
# one Home Assistant action each
SNOOZE_ACTIONS: Final[dict[str, tuple[CommandType, vol.Schema]]] = {
    "snooze": (
        CommandType.SNOOZE,
        vol.Schema({
            **SNOOZE_TARGET_FIELDS,
            vol.Optional("minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=SNOOZE_MAX_MINUTES)),
            vol.Optional("reason"): cv.string,
        }),
    ),
    "silence": (CommandType.SILENCE, vol.Schema({**SNOOZE_TARGET_FIELDS, vol.Optional("reason"): cv.string})),
    "unsnooze": (CommandType.NORMAL, vol.Schema(SNOOZE_TARGET_FIELDS)),
}

ATTR_KIND: Final[str] = "kind"
RESET_OVERRIDES_SCHEMA: Final = vol.Schema({vol.Optional(ATTR_KIND): vol.In(OVERRIDE_KINDS)})


def _json_safe(v: Any) -> Any:  # ruff: ignore[any-type]
    """Config as validated holds Template objects (e.g. a delivery's template conditions), which a
    service response can't serialize: give their source text instead, and lists for tuples/sets."""
    if isinstance(v, Template):
        return v.template
    if isinstance(v, dict):
        return {k: _json_safe(x) for k, x in v.items()}
    if isinstance(v, list | tuple | set):
        return [_json_safe(x) for x in v]
    return v


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

    async def action_notify(call: ServiceCall) -> JsonObjectType | None:
        """supernotify.notify - an alternative to notify.supernotify with each option that would
        otherwise be buried in the generic `data:` field promoted to its own schema-checked,
        selector-driven field (see NOTIFY_ACTION_SCHEMA/services.yaml). Also propagates the
        calling action's Context through to deliveries, same as the SuperNotificationService override
        of _async_notify_message_service does for notify.supernotify/notify.<target>.

        `dry_run` is a standard action-data field like priority/force_resend (see ATTR_DRY_RUN) -
        Notification.call_transport() is what actually skips sending, so there's no special case
        for it here. Requesting a response (supports_response=OPTIONAL) returns the notification's
        contents either way.
        """
        data = merge_delivery_fields(lift_legacy_nested_data(dict(call.data)))
        # extra_data is what Notification knows as `data`, and wins over any same-named key in a legacy `data`
        if extra_data := data.pop(ATTR_EXTRA_DATA, None):
            data[ATTR_DATA] = {**(data.get(ATTR_DATA) or {}), **extra_data}
        message = data.pop(CONF_MESSAGE, "")
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
        notification = await engine.async_send_message(message, title=title, target=target, data=data, context=call.context)
        return notification.contents() if notification else None

    def supplemental_action_enquire_configuration(_call: ServiceCall) -> dict[str, Any]:
        return _json_safe({
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
        })

    @callback
    def supplemental_action_refresh_entities(_call: ServiceCall) -> None:
        # a callback, so run in the event loop - it writes entity state
        engine.refresh_entities()

    @callback
    def supplemental_action_reset_overrides(call: ServiceCall) -> dict[str, Any]:
        # a callback, so run in the event loop - it writes entity state
        kind: str | None = call.data.get(ATTR_KIND)
        return {"reset": engine.reset_overrides((kind,) if kind else OVERRIDE_KINDS, call.context)}

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

    @callback
    def snooze_command(cmd: CommandType, call: ServiceCall) -> dict[str, Any]:
        """supernotify.snooze, supernotify.silence and supernotify.unsnooze - the same snooze, silence or
        unsnooze as a mobile action, voice sentence or the AI tool, for scripts, automations and dashboards,
        and open to any user, where firing the mobile action event over the API needs an admin. Run in the
        event loop like the others that change state."""
        scope = SNOOZE_SCOPES[call.data["scope"]]
        name: str | None = call.data.get("name")
        if isinstance(scope, QualifiedTargetType):
            if error := snooze_name_error(engine, scope, name, cmd):
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="invalid_snooze", translation_placeholders={"error": error}
                )
        else:
            name = None
        person: str | None = call.data.get("person")
        if person and person not in engine.context.people_registry.people:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_snooze",
                translation_placeholders={"error": f"{person} is not a recipient"},
            )
        minutes: int | None = call.data.get("minutes")
        snoozer = engine.context.snoozer
        snoozer.register_snooze(
            cmd,
            scope,
            name,
            RecipientType.USER if person else RecipientType.EVERYONE,
            person,
            dt.timedelta(minutes=minutes) if minutes else snoozer.snooze_period,
            reason=call.data.get("reason") or SNOOZE_REASON,
        )
        return {"snoozes": engine.enquire_snoozes()}

    def supplemental_action_enquire_recipients(_call: ServiceCall) -> dict[str, Any]:
        return {"recipients": engine.enquire_recipients()}

    async def supplemental_action_enquire_archive(call: ServiceCall) -> dict[str, Any]:
        archive = engine.context.archive
        if not archive.enabled or not archive.archive_directory:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_archive_configured",
            )
        notification_id: str | None = call.data.get("id")
        verbosity: str = call.data.get("verbosity") or (VERBOSITY_FULL if notification_id else VERBOSITY_STANDARD)

        def at_verbosity(contents: dict[str, Any]) -> dict[str, Any]:
            if verbosity == VERBOSITY_SUMMARY:
                return summarize_notification(engine, contents)
            if verbosity == VERBOSITY_STANDARD:
                return {k: v for k, v in contents.items() if k != "debug_trace"}
            return contents

        if notification_id:
            entry = await archive.archive_directory.read_entry(notification_id)
            if entry is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="archive_entry_not_found",
                    translation_placeholders={"notification_id": notification_id},
                )
            return summarize_by_day([entry]) if verbosity == VERBOSITY_DAILY else at_verbosity(entry)
        daily: bool = verbosity == VERBOSITY_DAILY
        limit: int = int(call.data["limit"]) if "limit" in call.data else (sys.maxsize if daily else 20)
        after_raw: str | None = call.data.get("after")
        before_raw: str | None = call.data.get("before")
        outcome: str | None = call.data.get("outcome")
        period: str | None = call.data.get("period")
        # a date/time given without a time zone is local time
        after = dt_util.as_local(dt.datetime.fromisoformat(after_raw)) if after_raw else None
        before = dt_util.as_local(dt.datetime.fromisoformat(before_raw)) if before_raw else None
        if after is None and period:
            after = dt_util.now() - ARCHIVE_PERIODS[period]
        entries = await archive.archive_directory.list_entries(limit=limit, after=after, before=before, outcome=outcome)
        if daily:
            return summarize_by_day(entries)
        return {"notifications": [at_verbosity(entry) for entry in entries], "count": len(entries)}

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
        supports_response=SupportsResponse.OPTIONAL,
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
        "enquire_archive",
        supplemental_action_enquire_archive,
        schema=ENQUIRE_ARCHIVE_SCHEMA,
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
    for action_name, (cmd, schema) in SNOOZE_ACTIONS.items():
        hass.services.async_register(
            DOMAIN,
            action_name,
            callback(partial(snooze_command, cmd)),
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
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

    services.yaml can only hold a fixed description, so it's copied and set again with the delivery
    and scenario fields as dropdowns, still taking a typed name. The delivery field is pre-filled
    with the implicit deliveries - what's used when it's left out - to add to or take from - and
    offers only deliveries with `default` or `explicit` inclusion, not scenario-only ones. Tuning
    deliveries, which needs a mapping, has its own free-form Delivery Control field - see
    merge_delivery_fields().
    Names and descriptions still come from the translations, which are looked up by field.
    Called on every config entry setup, so a reload picks up changed names.
    """
    integration = await async_get_integration(hass, DOMAIN)
    services: dict[str, Any] = await hass.async_add_executor_job(load_yaml_dict, str(integration.file_path / "services.yaml"))
    notify: dict[str, Any] = services["notify"]
    fields: dict[str, Any] = notify["fields"]
    if deliveries := list(engine.context.delivery_registry.choosable_deliveries):
        fields[ATTR_DELIVERY]["selector"] = {"select": {"options": deliveries, "multiple": True, "custom_value": True}}
        fields[ATTR_DELIVERY]["default"] = [d.name for d in engine.context.delivery_registry.implicit_deliveries]
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
