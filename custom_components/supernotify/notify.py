"""Supernotify service, extending BaseNotificationService"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Final, cast

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

from . import DOMAIN
from .archive import ARCHIVE_PURGE_MIN_INTERVAL
from .common import ensure_list
from .const import (
    ATTR_CUSTOM_TARGET,
    ATTR_MEDIA,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
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
    CONF_SCENARIOS,
    CONF_SNOOZE,
    CONF_TEMPLATE_PATH,
    CONF_TITLE,
    CONF_TRANSPORTS,
)
from .engine import SupernotifyEngine
from .model import NotifyEntityPlatform, Target
from .schema import NOTIFY_ACTION_SCHEMA

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

    from . import SupernotifyConfigEntry

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

SUPPLEMENTAL_SERVICE_NAMES: Final[tuple[str, ...]] = (
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
)


@callback
def async_register_supplemental_services(hass: HomeAssistant, engine: SupernotifyEngine, config: ConfigType) -> None:
    """Register the domain-scoped supplemental/debugging/admin services.

    Shared by the legacy YAML platform (async_get_service, below) and the config-entry setup
    (async_setup_entry in __init__.py), so both setup paths expose the same services. These
    are DOMAIN-scoped, not per config entry, so registration is guarded against being run
    twice - see SUPPLEMENTAL_SERVICE_NAMES/async_unregister_supplemental_services for the
    matching teardown.

    enquire_configuration closes over the raw config dict rather than `service`, because
    several of the fields it reports (delivery/transport/archive/dupe_check config, the full
    set of configured scenarios/recipients) are either private on the registries after
    initialize() or lossily reduced to derived values there - so `service` alone can't
    reconstruct them.
    """
    if hass.services.has_service(DOMAIN, "enquire_configuration"):
        return

    async def supplemental_action_notify(call: ServiceCall) -> None:
        """supernotify.notify - an alternative to notify.supernotify with each option that would
        otherwise be buried in the generic `data:` field promoted to its own schema-checked,
        selector-driven field (see NOTIFY_ACTION_SCHEMA/services.yaml). Also propagates the
        calling action's Context through to deliveries, same as the SuperNotificationService override
        of _async_notify_message_service does for notify.supernotify/notify.<target>.
        """
        data = dict(call.data)
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
            CONF_TRANSPORTS: config.get(CONF_TRANSPORTS, {}),
            CONF_CAMERAS: config.get(CONF_CAMERAS, {}),
            CONF_DUPE_CHECK: config.get(CONF_DUPE_CHECK, {}),
            CONF_SNOOZE: config.get(CONF_SNOOZE, {}),
        }

    def supplemental_action_refresh_entities(_call: ServiceCall) -> None:
        return engine.expose_entities()

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
            raise ServiceValidationError("No archive configured")
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
            raise ServiceValidationError("No media storage configured")
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
        supplemental_action_notify,
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


@callback
def async_unregister_supplemental_services(hass: HomeAssistant) -> None:
    """Undo async_register_supplemental_services."""
    for name in SUPPLEMENTAL_SERVICE_NAMES:
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Legacy `notify: - platform: supernotify` entrypoint - see async_setup_legacy in legacy
    BaseNotificationService.

    The config entry is now the sole, unconditional owner of notify.supernotify (see
    async_setup_entry in __init__.py), so this leftover legacy YAML block never builds or
    registers a service any more - it only raises a fixable repair pointing at the migration
    (see repairs.py) and declines to set up (returning None is HA's supported "decline" path for
    a legacy notify platform - a clean one-line log, no exception).

    A `name:` in this leftover block still gets synced onto the owning entry every load though
    (not gated behind that repair), and likewise for its template_path/media_path/etc and
    archive/dupe_check/housekeeping settings - otherwise an entry auto-bootstrapped blank by
    async_setup (see __init__.py), which happens before anyone gets around to opening and
    confirming the migration repair, would keep running on defaults with nothing configured,
    silently breaking automations, template/media paths and archiving on every restart until the
    repair is manually confirmed. That repair is only ever needed for delivery/transports/
    scenarios/etc - a "simple" install with none of that has no reason to see it at all, so this
    core migration must not depend on it.
    """
    _ = discovery_info

    from .repairs import async_create_legacy_yaml_issue, async_sync_entry_from_legacy_config

    legacy_config = dict(config)
    async_sync_entry_from_legacy_config(hass, legacy_config)
    async_create_legacy_yaml_issue(hass, legacy_config)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SupernotifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose each configured recipient as its own notify entity.

    Forwarded to from async_setup_entry in __init__.py once the SupernotifyEngine (entry.
    runtime_data) is fully initialized, so people_registry is already populated.
    """
    # _ = hass
    entry.runtime_data.context.people_registry.expose_notify_entities(
        entry.entry_id, async_add_entities, cast(NotifyEntityPlatform, entry.runtime_data)
    )
