from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import (
    NotifyEntity,
    NotifyEntityFeature,
)
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.const import (
    CONF_TARGET,
)
from homeassistant.core import (
    ServiceCall,
)

from .const import (
    ATTR_DATA,
    CONF_MESSAGE,
    CONF_TITLE,
)
from .engine import SupernotifyEngine

_LOGGER = logging.getLogger(__name__)


class SupernotifyEntity(NotifyEntity):
    """Implement supernotify as a NotifyEntity platform."""

    _attr_has_entity_name = True
    _attr_name = "supernotify"

    def __init__(
        self,
        unique_id: str,
        platform: SupernotifyEngine,
    ) -> None:
        """Initialize the SuperNotify entity."""
        self._attr_unique_id = unique_id
        self._attr_supported_features = NotifyEntityFeature.TITLE
        self._platform = platform

    async def async_send_message(
        self, message: str, title: str | None = None, target: str | list[str] | None = None, data: dict[str, Any] | None = None
    ) -> None:
        """Send a message to a user."""
        await self._platform.async_send_message(message, title=title, target=target, data=data, context=self._context)


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
