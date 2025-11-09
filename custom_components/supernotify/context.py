from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.typing import ConfigType

if TYPE_CHECKING:
    from .archive import NotificationArchive
    from .scenario import ScenarioRegistry
    from .snoozer import Snoozer
from homeassistant.helpers import condition as condition

from . import (
    CONF_CAMERA,
)
from .common import ensure_list

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

    from .delivery import DeliveryRegistry
    from .hass_api import HomeAssistantAPI
    from .people import PeopleRegistry
    from .transport import Transport


_LOGGER = logging.getLogger(__name__)


class Context:
    def __init__(
        self,
        hass_api: HomeAssistantAPI,
        people_registry: PeopleRegistry,
        scenario_registry: ScenarioRegistry,
        delivery_registry: DeliveryRegistry,
        archive: NotificationArchive,
        snoozer: Snoozer,
        links: list[str] | None = None,
        recipients: list[dict[str, Any]] | None = None,
        mobile_actions: ConfigType | None = None,
        template_path: str | None = None,
        media_path: str | None = None,
        cameras: list[ConfigType] | None = None,
    ) -> None:
        self.delivery_registry: DeliveryRegistry = delivery_registry
        self.snoozer: Snoozer = snoozer
        self.people_registry: PeopleRegistry = people_registry
        self.scenario_registry: ScenarioRegistry = scenario_registry
        self.archive: NotificationArchive = archive
        self.hass_api: HomeAssistantAPI = hass_api
        self.links: list[dict[str, Any]] = ensure_list(links)

        self._recipients: list[dict[str, Any]] = ensure_list(recipients)
        self.mobile_actions: ConfigType = mobile_actions or {}
        self.template_path: Path | None = Path(template_path) if template_path else None
        self.media_path: Path | None = Path(media_path) if media_path else None

        self.cameras: dict[str, Any] = {c[CONF_CAMERA]: c for c in cameras} if cameras else {}
        self.snoozer = snoozer

    async def initialize(self) -> None:
        if self.template_path and not self.template_path.exists():
            _LOGGER.warning("SUPERNOTIFY template path not found at %s", self.template_path)
            self.template_path = None

        if self.media_path and not self.media_path.exists():
            _LOGGER.info("SUPERNOTIFY media path not found at %s", self.media_path)
            try:
                self.media_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY media path %s cannot be created: %s", self.media_path, e)
                self.hass_api.raise_issue("media_path", "media_path", {"path": str(self.media_path), "error": str(e)})
                self.media_path = None
        if self.media_path is not None:
            _LOGGER.info("SUPERNOTIFY abs media path: %s", self.media_path.absolute())

    def configure_for_tests(
        self, transport_instances: list[Transport] | None = None, create_default_scenario: bool = False
    ) -> None:
        self.scenario_registry.default_scenario_for_testing = create_default_scenario
        self.delivery_registry._transport_instances = transport_instances
