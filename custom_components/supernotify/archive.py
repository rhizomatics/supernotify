import datetime as dt
import json
import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles.os
import anyio
import homeassistant.util.dt as dt_util
from homeassistant.const import (
    CONF_DEBUG,
    CONF_ENABLED,
)
from homeassistant.helpers import condition as condition

from .const import (
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_DIAGNOSTICS,
    CONF_ARCHIVE_EVENT_NAME,
    CONF_ARCHIVE_EVENT_SELECTION,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_ARCHIVE_PURGE_INTERVAL,
)
from .schema import Outcome, OutcomeSelection

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)

ARCHIVE_PURGE_MIN_INTERVAL = 3 * 60
ARCHIVE_DEFAULT_DAYS = 1
WRITE_TEST = ".startup"


class ArchivableObject:
    @abstractmethod
    def base_filename(self) -> str:
        pass

    @abstractmethod
    def contents(self, diagnostics: bool = False, **_kwargs: Any) -> Any:
        pass

    def outcome(self) -> Outcome:
        return Outcome.NO_DELIVERY

    def selected(self, outcome_policy: OutcomeSelection) -> bool:
        if outcome_policy & OutcomeSelection.NONE:
            return False
        return bool(
            outcome_policy & OutcomeSelection.ALL
            or (outcome_policy & OutcomeSelection.SUCCESS and self.outcome() == Outcome.SUCCESS)
            or (outcome_policy & OutcomeSelection.NO_DELIVERY and self.outcome() == Outcome.NO_DELIVERY)
            or (outcome_policy & OutcomeSelection.PARTIAL_DELIVERY and self.outcome() == Outcome.PARTIAL_DELIVERY)
            or (outcome_policy & OutcomeSelection.DUPE and self.outcome() == Outcome.DUPE)
            or (outcome_policy & OutcomeSelection.FALLBACK_DELIVERY and self.outcome() == Outcome.FALLBACK_DELIVERY)
            or (outcome_policy & OutcomeSelection.ERROR and self.outcome() == Outcome.ERROR)
        )


class ArchiveDestination:
    @abstractmethod
    async def archive(self, archive_object: ArchivableObject) -> bool:
        pass


class EventArchiver(ArchiveDestination):
    def __init__(
        self, hass_api: HomeAssistantAPI, event_name: str, diagnostics: OutcomeSelection = OutcomeSelection.ERROR
    ) -> None:
        self.hass_api = hass_api
        self.event_name = event_name
        self.diagnostics = diagnostics
        if diagnostics & OutcomeSelection.NONE:
            pass
        elif diagnostics & OutcomeSelection.ALL:
            _LOGGER.info("SUPERNOTIFY archiving all notifications as %s events", event_name)
        else:
            if diagnostics & OutcomeSelection.SUCCESS:
                _LOGGER.info("SUPERNOTIFY archiving successful notifications as %s events", event_name)
            if diagnostics & OutcomeSelection.PARTIAL_DELIVERY:
                _LOGGER.info("SUPERNOTIFY archiving partial delivery notifications as %s events", event_name)

            if diagnostics & OutcomeSelection.FALLBACK_DELIVERY:
                _LOGGER.info("SUPERNOTIFY archiving fallback notifications as %s events", event_name)
            if diagnostics & OutcomeSelection.NO_DELIVERY:
                _LOGGER.info("SUPERNOTIFY archiving no delivery notifications as %s events", event_name)

            if diagnostics & OutcomeSelection.ERROR:
                _LOGGER.info("SUPERNOTIFY archiving error notifications as %s events", event_name)

            if diagnostics & OutcomeSelection.DUPE:
                _LOGGER.info("SUPERNOTIFY archiving dupe notifications as %s events", event_name)

    async def archive(self, archive_object: ArchivableObject) -> bool:
        payload = archive_object.contents(diagnostics=archive_object.selected(self.diagnostics))
        self.hass_api.fire_event(self.event_name, payload)
        return True


class ArchiveTopic(ArchiveDestination):
    def __init__(
        self,
        hass_api: HomeAssistantAPI,
        topic: str,
        qos: int = 0,
        retain: bool = True,
        diagnostics: OutcomeSelection = OutcomeSelection.ERROR,
    ) -> None:
        self.hass_api: HomeAssistantAPI = hass_api
        self.topic: str = topic
        self.qos: int = qos
        self.retain: bool = retain
        self.diagnostics: OutcomeSelection = diagnostics
        self.enabled: bool = False

    async def initialize(self) -> None:
        if await self.hass_api.mqtt_available(raise_on_error=False):
            _LOGGER.info(f"SUPERNOTIFY Archiving to MQTT topic {self.topic}, qos {self.qos}, retain {self.retain}")
            self.enabled = True
        else:
            _LOGGER.warning(
                f"SUPERNOTIFY archiving configured for topic {self.topic} but MQTTT not available at startup, disabled"
            )

    async def archive(self, archive_object: ArchivableObject) -> bool:
        if not self.enabled:
            return False
        payload = archive_object.contents(diagnostics=archive_object.selected(self.diagnostics))
        topic = f"{self.topic}/{archive_object.base_filename()}"
        _LOGGER.debug(f"SUPERNOTIFY Publishing notification to {topic}")
        try:
            await self.hass_api.mqtt_publish(
                topic=topic,
                payload=payload,
                qos=self.qos,
                retain=self.retain,
            )
            return True
        except Exception:
            _LOGGER.warning(f"SUPERNOTIFY failed to archive to topic {self.topic}")
            return False


class ArchiveDirectory(ArchiveDestination):
    def __init__(self, path: str, purge_minute_interval: int, diagnostics: OutcomeSelection = OutcomeSelection.ERROR) -> None:
        self.configured_path: str = path
        self.archive_path: anyio.Path | None = None
        self.enabled: bool = False
        self.diagnostics: OutcomeSelection = diagnostics
        self.last_purge: dt.datetime | None = None
        self.purge_minute_interval: int = purge_minute_interval

    async def initialize(self) -> None:
        verify_archive_path: anyio.Path = anyio.Path(self.configured_path)
        if verify_archive_path and not await verify_archive_path.exists():
            _LOGGER.info("SUPERNOTIFY archive path not found at %s", verify_archive_path)
            try:
                await verify_archive_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY archive path %s cannot be created: %s", verify_archive_path, e)
        if verify_archive_path and await verify_archive_path.exists() and await verify_archive_path.is_dir():
            try:
                await verify_archive_path.joinpath(WRITE_TEST).touch(exist_ok=True)
                self.archive_path = verify_archive_path
                _LOGGER.info("SUPERNOTIFY archiving notifications to file system at %s", verify_archive_path)
                self.enabled = True
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY archive path %s cannot be written: %s", verify_archive_path, e)
        else:
            _LOGGER.warning("SUPERNOTIFY archive path %s is not a directory or does not exist", verify_archive_path)

    async def archive(self, archive_object: ArchivableObject) -> bool:
        archived: bool = False

        if self.enabled and self.archive_path:  # archive_path to assuage mypy
            archive_filepath: anyio.Path | None = None
            diagnostics: bool = archive_object.selected(self.diagnostics)
            try:
                filename = f"{archive_object.base_filename()}.json"
                archive_filepath = self.archive_path.joinpath(filename)
                serialized: str = json.dumps(archive_object.contents(diagnostics=diagnostics), indent=2)
                async with aiofiles.open(archive_filepath, mode="w") as file:
                    await file.write(serialized)
                _LOGGER.debug("SUPERNOTIFY Archived notification %s", await archive_filepath.absolute())
                archived = True
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to archive notification: %s", e)
                if diagnostics and archive_filepath:
                    try:
                        serialized = json.dumps(archive_object.contents(diagnostics=False), indent=2)
                        async with aiofiles.open(archive_filepath, mode="w") as file:
                            await file.write(serialized)
                        _LOGGER.warning("SUPERNOTIFY Archived minimal notification %s", await archive_filepath.absolute())
                        archived = True
                    except Exception as e2:
                        _LOGGER.exception("SUPERNOTIFY Unable to archive minimal notification: %s", e2)
        return archived

    async def size(self) -> int:
        path = self.archive_path
        if path and await path.exists():
            return sum(1 for p in await aiofiles.os.listdir(path) if p != WRITE_TEST)
        return 0

    async def cleanup(self, days: int, force: bool) -> int:
        if (
            not force
            and self.last_purge is not None
            and self.last_purge > dt.datetime.now(dt.UTC) - dt.timedelta(minutes=self.purge_minute_interval)
        ):
            return 0

        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
        cutoff = cutoff.astimezone(dt.UTC)
        purged = 0
        if self.archive_path and await self.archive_path.exists():
            try:
                archive = await aiofiles.os.scandir(self.archive_path)
                for entry in archive:
                    if entry.name == ".startup":
                        continue
                    if dt_util.utc_from_timestamp(entry.stat().st_ctime) <= cutoff:
                        _LOGGER.debug("SUPERNOTIFY Purging %s", entry.path)
                        await aiofiles.os.unlink(Path(entry.path))
                        purged += 1
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to clean up archive at %s: %s", self.archive_path, e, exc_info=True)
            _LOGGER.info("SUPERNOTIFY Purged %s archived notifications for cutoff %s", purged, cutoff)
            self.last_purge = dt.datetime.now(dt.UTC)
        else:
            _LOGGER.debug("SUPERNOTIFY Skipping archive purge for unknown path %s", self.archive_path)
        return purged


class NotificationArchive:
    def __init__(
        self,
        config: ConfigType,
        hass_api: HomeAssistantAPI,
    ) -> None:
        self.hass_api = hass_api
        self.enabled = bool(config.get(CONF_ENABLED, False))
        self.archive_directory: ArchiveDirectory | None = None
        self.archive_topic: ArchiveTopic | None = None
        self.event_archiver: EventArchiver | None = None
        self.event_selection: OutcomeSelection = config.get(CONF_ARCHIVE_EVENT_SELECTION, OutcomeSelection.NONE)
        self.diagnostics: OutcomeSelection = config.get(CONF_ARCHIVE_DIAGNOSTICS, OutcomeSelection.ERROR)
        self.archive_event_name: str = config.get(CONF_ARCHIVE_EVENT_NAME, "supernotification")
        self.configured_archive_path: str | None = config.get(CONF_ARCHIVE_PATH)
        self.archive_days = int(config.get(CONF_ARCHIVE_DAYS, ARCHIVE_DEFAULT_DAYS))
        self.mqtt_topic: str | None = config.get(CONF_ARCHIVE_MQTT_TOPIC)
        self.mqtt_qos: int = int(config.get(CONF_ARCHIVE_MQTT_QOS, 0))
        self.mqtt_retain: bool = bool(config.get(CONF_ARCHIVE_MQTT_RETAIN, True))
        self.debug: bool = bool(config.get(CONF_DEBUG, False))

        self.purge_minute_interval = int(config.get(CONF_ARCHIVE_PURGE_INTERVAL, ARCHIVE_PURGE_MIN_INTERVAL))

    async def initialize(self) -> None:
        if not self.enabled:
            _LOGGER.info("SUPERNOTIFY Archive disabled")
            return
        if not self.configured_archive_path:
            _LOGGER.warning("SUPERNOTIFY archive path not configured")
        else:
            self.archive_directory = ArchiveDirectory(
                self.configured_archive_path, purge_minute_interval=self.purge_minute_interval, diagnostics=self.diagnostics
            )
            await self.archive_directory.initialize()

        if self.mqtt_topic is not None:
            self.archive_topic = ArchiveTopic(self.hass_api, self.mqtt_topic, self.mqtt_qos, self.mqtt_retain, self.diagnostics)
            await self.archive_topic.initialize()

        self.event_archiver = EventArchiver(self.hass_api, self.archive_event_name, self.diagnostics)

    async def size(self) -> int:
        return await self.archive_directory.size() if self.archive_directory else 0

    async def cleanup(self, days: int | None = None, force: bool = False) -> int:
        days = days or self.archive_days
        return await self.archive_directory.cleanup(days, force) if self.archive_directory else 0

    async def archive(self, archive_object: ArchivableObject) -> bool:
        archived: bool = False
        if self.archive_topic:
            if await self.archive_topic.archive(archive_object):
                archived = True
        if self.archive_directory:
            if await self.archive_directory.archive(archive_object):
                archived = True
        if self.event_archiver and archive_object.selected(self.event_selection):
            await self.event_archiver.archive(archive_object)

        return archived
