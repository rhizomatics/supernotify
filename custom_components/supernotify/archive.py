import datetime as dt
import logging
from abc import abstractmethod
from pathlib import Path
from typing import Any

import aiofiles.os
import anyio
import homeassistant.util.dt as dt_util
from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import save_json

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
    def __init__(self, hass: HomeAssistant, topic: str, qos: int = 0, retain: bool = True) -> None:
        self._hass = hass
        self.topic = topic
        self.qos = qos
        self.retain = retain

    async def publish(self, archive_object: ArchivableObject) -> None:
        payload = archive_object.contents(minimal=True)
        _LOGGER.debug("SUPERNOTIFY Publishing notification to %s", self.topic)
        await mqtt.async_publish(self._hass, self.topic, payload, qos=self.qos, retain=self.retain)


class NotificationArchive:
    def __init__(
        self, enabled: bool, archive_path: str | None, archive_days: str | None, purge_minute_interval: str | None = None
    ) -> None:
        self.enabled = enabled
        self.last_purge: dt.datetime | None = None
        self.configured_archive_path: str | None = archive_path
        self.archive_path: Path | None = None
        self.archive_days: int = int(archive_days) if archive_days else ARCHIVE_DEFAULT_DAYS
        self.purge_minute_interval = int(purge_minute_interval) if purge_minute_interval else ARCHIVE_PURGE_MIN_INTERVAL

    def initialize(self) -> None:
        if not self.enabled:
            _LOGGER.info("SUPERNOTIFY Archive disabled")
            return
        if not self.configured_archive_path:
            _LOGGER.warning("SUPERNOTIFY archive path not configured")
            return
        verify_archive_path: Path = Path(self.configured_archive_path)
        if verify_archive_path and not verify_archive_path.exists():
            _LOGGER.info("SUPERNOTIFY archive path not found at %s", verify_archive_path)
            try:
                verify_archive_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY archive path %s cannot be created: %s", verify_archive_path, e)
        if verify_archive_path and verify_archive_path.exists() and verify_archive_path.is_dir():
            try:
                verify_archive_path.joinpath(WRITE_TEST).touch(exist_ok=True)
                self.archive_path = verify_archive_path
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY archive path %s cannot be written: %s", verify_archive_path, e)
                self.enabled = False
        else:
            _LOGGER.warning("SUPERNOTIFY archive path %s is not a directory or does not exist", verify_archive_path)
            self.enabled = False

    async def size(self) -> int:
        path = self.archive_path
        if path and await anyio.Path(path).exists():
            return sum(1 for p in await aiofiles.os.listdir(path) if p != WRITE_TEST)
        return 0

    async def cleanup(self, days: int | None = None, force: bool = False) -> int:
        if (
            not force
            and self.last_purge is not None
            and self.last_purge > dt.datetime.now(dt.UTC) - dt.timedelta(minutes=self.purge_minute_interval)
        ):
            return 0
        days = days or self.archive_days

        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=self.archive_days)
        cutoff = cutoff.astimezone(dt.UTC)
        purged = 0
        if self.archive_path and await anyio.Path(self.archive_path).exists():
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

    def archive(self, archive_object: ArchivableObject) -> bool:
        if not self.enabled or not self.archive_path:
            return False
        archive_path: str = ""
        try:
            filename = f"{archive_object.base_filename()}.json"
            archive_path = str(self.archive_path.joinpath(filename))
            save_json(archive_path, archive_object.contents())
            _LOGGER.debug("SUPERNOTIFY Archived notification %s", archive_path)
            return True
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to archive notification: %s", e)
            try:
                save_json(archive_path, archive_object.contents(minimal=True))
                _LOGGER.debug("SUPERNOTIFY Archived minimal notification %s", archive_path)
                return True
            except Exception as e2:
                _LOGGER.warning("SUPERNOTIFY Unable to archive minimal notification: %s", e2)
        return False
