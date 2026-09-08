from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.const import (
    CONF_TARGET,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
)

from .engine import SupernotifyEngine
from .model import NotifyEntityPlatform

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

    from . import SupernotifyConfigEntry
from .const import (
    ATTR_DATA,
    CONF_MESSAGE,
    CONF_TITLE,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


class SuperNotificationService(BaseNotificationService):
    """Legacy notify-platform compatibility shim.

    The only reason this exists is to satisfy HA core's notify/legacy.py
    BaseNotificationService contract, so notify.supernotify and notify.<target> keep working.
    It adds nothing but that glue on top of SupernotifyEngine - nothing else in this
    integration (SupernotifyEntity, RecipientNotifyEntity, the supplemental actions, tests
    targeting the engine) references this class or BaseNotificationService. If/when HA core
    drops BaseNotificationService, delete this class and the matching async_setup/
    async_register_services/async_unregister_services calls in __init__.py; everything else
    keeps working unchanged.
    """

    def __init__(self, engine: SupernotifyEngine, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.engine = engine

    async def async_unregister_services(self) -> None:
        _LOGGER.info("SUPERNOTIFY Unregistering notify service")
        return await super().async_unregister_services()

    async def _async_notify_message_service(self, service: ServiceCall) -> None:
        """Override of BaseNotificationService._async_notify_message_service (notify/legacy.py)
        to forward the calling action's Context through to async_send_message. HA core's
        implementation builds its own kwargs from service.data and drops service.context
        entirely, which is why every notify.supernotify/notify.<target> call otherwise loses
        its link back to the triggering automation, showing up downstream (e.g. in the mobile
        app's notification history) as having no recorded cause.
        """
        kwargs: dict[str, Any] = {}
        message: str = service.data[CONF_MESSAGE]
        if title := service.data.get(CONF_TITLE):
            kwargs[CONF_TITLE] = title
        if self.registered_targets.get(service.service) is not None:
            kwargs[CONF_TARGET] = [self.registered_targets[service.service]]
        elif service.data.get(CONF_TARGET) is not None:
            kwargs[CONF_TARGET] = service.data.get(CONF_TARGET)
        kwargs[CONF_MESSAGE] = message
        kwargs[ATTR_DATA] = service.data.get(ATTR_DATA)
        kwargs["context"] = service.context

        await self.engine.async_send_message(**kwargs)


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
