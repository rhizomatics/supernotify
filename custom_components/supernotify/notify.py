from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.components.notify.const import NOTIFY_SERVICE_SCHEMA
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.const import (
    CONF_NAME,
    CONF_TARGET,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from . import DOMAIN, NOTIFY_SERVICE_NAME
from .common import ensure_list
from .engine import SupernotifyEngine
from .model import NotifyEntityPlatform

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

    from . import SupernotifyConfigEntry
from .const import (
    ATTR_DATA,
    ATTR_DELIVERY,
    ATTR_SCENARIOS_APPLY,
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


class ExposedNotifyEntity(NotifyEntity):
    """A scenario or delivery exposed as its own `notify.<notify_entity>` entity.

    Sending to it is a plain notification, to the default recipients, with only the scenario
    applied, or the delivery selected, as `data` gives. Per HA's notify entity service schema,
    only message/title are ever passed in here.
    """

    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, unique_id: str, entity_id: str, name: str, engine: SupernotifyEngine, data: dict[str, Any]) -> None:
        self._attr_unique_id = unique_id
        self._attr_name = name
        self.entity_id = entity_id
        self._engine = engine
        self._data = data

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self._engine.async_send_message(message, title=title, context=self._context, data=dict(self._data))


def exposed_notify_entities(
    hass: HomeAssistant, entry_id: str, engine: SupernotifyEngine, reserved: str = NOTIFY_SERVICE_NAME
) -> list[ExposedNotifyEntity]:
    """An entity for each scenario and delivery with a `notify_entity`, other than where its
    `notify.<notify_entity>` is already taken, by an entity or a notify action, which gets a
    repair instead. An entity left from a `notify_entity` no longer configured is removed.

    `reserved` is the name of the main notify action, which isn't registered until after this.
    """
    registry = er.async_get(hass)
    context = engine.context
    # recipients are added alongside, so may not be registered yet
    taken: set[str] = {f"{NOTIFY_DOMAIN}.{reserved}"} | {
        f"{NOTIFY_DOMAIN}.recipient_{r.name}" for r in context.people_registry.people.values()
    }
    entities: dict[str, ExposedNotifyEntity] = {}
    for kind, data_key, configured in (
        ("scenario", ATTR_SCENARIOS_APPLY, context.scenario_registry.scenarios),
        ("delivery", ATTR_DELIVERY, context.delivery_registry.deliveries),
    ):
        for name, exposable in configured.items():
            issue_id = f"notify_entity_{kind}_{name}"
            exposable.notify_entity_id = None
            if not exposable.notify_entity:
                context.hass_api.delete_issue(issue_id)
                continue
            unique_id = f"{entry_id}_{kind}_{name}"
            entity_id = f"{NOTIFY_DOMAIN}.{exposable.notify_entity}"
            registered: str | None = registry.async_get_entity_id(NOTIFY_DOMAIN, DOMAIN, unique_id)
            if (
                entity_id in taken
                or hass.services.has_service(NOTIFY_DOMAIN, exposable.notify_entity)
                or (
                    registered != entity_id
                    and (registry.async_get(entity_id) is not None or hass.states.get(entity_id) is not None)
                )
            ):
                _LOGGER.warning("SUPERNOTIFY %s already exists, so %s %s can't use it", entity_id, kind, name)
                context.hass_api.raise_issue(
                    issue_id,
                    issue_key="notify_entity_exists",
                    issue_map={"entity_id": entity_id, "kind": kind, "name": name},
                    learn_more_url=f"https://supernotify.rhizomatics.org.uk/configuration/{'scenarios' if kind == 'scenario' else 'deliveries'}/",
                )
                continue
            context.hass_api.delete_issue(issue_id)
            if registered is not None and registered != entity_id:
                # notify_entity has changed, and the registry would otherwise keep the old entity_id
                registry.async_update_entity(registered, new_entity_id=entity_id)
            taken.add(entity_id)
            exposable.notify_entity_id = entity_id
            entities[unique_id] = ExposedNotifyEntity(unique_id, entity_id, exposable.alias or name, engine, {data_key: [name]})
    for registered_entry in er.async_entries_for_config_entry(registry, entry_id):
        if (
            registered_entry.domain == NOTIFY_DOMAIN
            and registered_entry.unique_id.startswith((f"{entry_id}_scenario_", f"{entry_id}_delivery_"))
            and registered_entry.unique_id not in entities
        ):
            registry.async_remove(registered_entry.entity_id)
    return list(entities.values())


def async_register_entity_actions(
    hass: HomeAssistant, entry: SupernotifyConfigEntry, engine: SupernotifyEngine, targets: dict[str, str]
) -> None:
    """A legacy `notify.<name>` action alongside each notify entity, by action name and the target
    it stands for, for callers like the Alert integration that only know notify actions.

    The target goes through the same short circuit as when given to supernotify.notify, see
    convert_notify_entities() and convert_exposed_notify_entities() in notification.py.
    """
    for name, target in targets.items():
        if hass.services.has_service(NOTIFY_DOMAIN, name):
            _LOGGER.warning("SUPERNOTIFY notify.%s is already registered - not registering it again", name)
            continue

        async def notify(call: ServiceCall, target: str = target) -> None:
            await engine.async_send_message(
                call.data[CONF_MESSAGE],
                title=call.data.get(CONF_TITLE),
                target=[target, *ensure_list(call.data.get(CONF_TARGET))],
                context=call.context,
                data=call.data.get(ATTR_DATA),
            )

        hass.services.async_register(NOTIFY_DOMAIN, name, notify, schema=NOTIFY_SERVICE_SCHEMA)
        entry.async_on_unload(partial(hass.services.async_remove, NOTIFY_DOMAIN, name))


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
    """Expose each configured recipient as its own notify entity, and each scenario or delivery
    with a `notify_entity`, all with a legacy notify action of the same name.

    Forwarded to from async_setup_entry in __init__.py once the SupernotifyEngine (entry.
    runtime_data) is fully initialized, so people_registry is already populated.
    """
    engine: SupernotifyEngine = entry.runtime_data
    exposed = exposed_notify_entities(
        hass, entry.entry_id, engine, reserved=slugify(entry.data.get(CONF_NAME) or NOTIFY_SERVICE_NAME)
    )
    async_add_entities(exposed)
    engine.context.people_registry.expose_notify_entities(
        entry.entry_id, async_add_entities, cast(NotifyEntityPlatform, engine)
    )
    async_register_entity_actions(
        hass,
        entry,
        engine,
        {f"recipient_{r.name}": r.entity_id for r in engine.context.people_registry.people.values()}
        | {e.entity_id.partition(".")[2]: e.entity_id for e in exposed},
    )
