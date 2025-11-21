import datetime as dt
import logging
from abc import abstractmethod
from pathlib import Path
from typing import Any

import aiofiles.os
import anyio
import homeassistant.util.dt as dt_util
from homeassistant.const import CONF_ENABLED
from homeassistant.helpers import condition as condition
from homeassistant.helpers.json import save_json
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.hass_api import HomeAssistantAPI

from . import (
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
    CONF_ARCHIVE_PURGE_INTERVAL,
    CONF_DEBUG,
)

_LOGGER = logging.getLogger(__name__)

ARCHIVE_PURGE_MIN_INTERVAL = 3 * 60
ARCHIVE_DEFAULT_DAYS = 1
WRITE_TEST = ".startup"


class ArchivableObject:
    @abstractmethod
    def base_filename(self) -> str:
        pass

    def contents(self, minimal: bool = False) -> Any:
        pass


class ArchiveTopic:
    def __init__(self, hass_api: HomeAssistantAPI, topic: str, qos: int = 0, retain: bool = True, debug: bool = False) -> None:
        self.hass_api: HomeAssistantAPI = hass_api
        self.topic: str = topic
        self.qos: int = qos
        self.retain: bool = retain
        self.debug: bool = debug
        self.enabled: bool = False

    async def initialize(self) -> None:
        if await self.hass_api.mqtt_available(raise_on_error=False):
            _LOGGER.info(
                f"SUPERNOTIFY Archiving to MQTT topic {self.topic}, qos {self.qos}, retain {self.retain}"
            )
            self.enabled = True

    async def archive(self, archive_object: ArchivableObject) -> bool:
        if not self.enabled:
            return False
        payload = archive_object.contents(minimal=self.debug)
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
            _LOGGER.warning(
                f"SUPERNOTIFY failed to archive to topic {self.topic}")
            return False


class ArchiveDirectory:
    def __init__(self, path: str, purge_minute_interval: int, debug: bool) -> None:
        self.configured_path: str = path
        self.archive_path: anyio.Path | None = None
        self.enabled: bool = False
        self.debug: bool = debug
        self.last_purge: dt.datetime | None = None
        self.purge_minute_interval: int = purge_minute_interval

    async def initialize(self) -> None:
        verify_archive_path: anyio.Path = anyio.Path(
            self.configured_path)
        if verify_archive_path and not await verify_archive_path.exists():
            _LOGGER.info(
                "SUPERNOTIFY archive path not found at %s", verify_archive_path)
            try:
                await verify_archive_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning(
                    "SUPERNOTIFY archive path %s cannot be created: %s", verify_archive_path, e)
        if verify_archive_path and await verify_archive_path.exists() and await verify_archive_path.is_dir():
            try:
                await verify_archive_path.joinpath(WRITE_TEST).touch(exist_ok=True)
                self.archive_path = verify_archive_path
                _LOGGER.info(
                    "SUPERNOTIFY archiving notifications to file system at %s", verify_archive_path)
                self.enabled = True
            except Exception as e:
                _LOGGER.warning(
                    "SUPERNOTIFY archive path %s cannot be written: %s", verify_archive_path, e)
        else:
            _LOGGER.warning(
                "SUPERNOTIFY archive path %s is not a directory or does not exist", verify_archive_path)

    async def archive(self, archive_object: ArchivableObject) -> bool:
        archived: bool = False

        if self.enabled:
            archive_path: str = ""
            try:
                filename = f"{archive_object.base_filename()}.json"
                archive_path = str(self.archive_path.joinpath(filename))
                save_json(archive_path, archive_object.contents(
                    minimal=self.debug))
                _LOGGER.debug(
                    "SUPERNOTIFY Archived notification %s", archive_path)
                archived = True
            except Exception as e:
                _LOGGER.warning(
                    "SUPERNOTIFY Unable to archive notification: %s", e)
                if self.debug:
                    try:
                        save_json(archive_path,
                                  archive_object.contents(minimal=self.debug))
                        _LOGGER.warning(
                            "SUPERNOTIFY Archived minimal notification %s", archive_path)
                        archived = True
                    except Exception as e2:
                        _LOGGER.exception(
                            "SUPERNOTIFY Unable to archive minimal notification: %s", e2)
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
                _LOGGER.warning(
                    "SUPERNOTIFY Unable to clean up archive at %s: %s", self.archive_path, e, exc_info=True)
            _LOGGER.info(
                "SUPERNOTIFY Purged %s archived notifications for cutoff %s", purged, cutoff)
            self.last_purge = dt.datetime.now(dt.UTC)
        else:
            _LOGGER.debug(
                "SUPERNOTIFY Skipping archive purge for unknown path %s", self.archive_path)
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
        self.configured_archive_path: str | None = config.get(
            CONF_ARCHIVE_PATH)
        self.archive_days = int(config.get(
            CONF_ARCHIVE_DAYS, ARCHIVE_DEFAULT_DAYS))
        self.mqtt_topic: str | None = config.get(CONF_ARCHIVE_MQTT_TOPIC)
        self.mqtt_qos: int = int(config.get(CONF_ARCHIVE_MQTT_QOS, 0))
        self.mqtt_retain: bool = bool(
            config.get(CONF_ARCHIVE_MQTT_RETAIN, True))
        self.debug: bool = bool(config.get(CONF_DEBUG, False))

        self.purge_minute_interval = int(config.get(
            CONF_ARCHIVE_PURGE_INTERVAL, ARCHIVE_PURGE_MIN_INTERVAL))

    async def initialize(self) -> None:
        if not self.enabled:
            _LOGGER.info("SUPERNOTIFY Archive disabled")
            return
        if not self.configured_archive_path:
            _LOGGER.warning("SUPERNOTIFY archive path not configured")
        else:
            self.archive_directory = ArchiveDirectory(
                self.configured_archive_path,
                purge_minute_interval=self.purge_minute_interval,
                debug=self.debug)
            await self.archive_directory.initialize()

        if self.mqtt_topic is not None:
            self.archive_topic = ArchiveTopic(
                self.hass_api, self.mqtt_topic, self.mqtt_qos, self.mqtt_retain, self.debug)
            await self.archive_topic.initialize()

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

        return archived
