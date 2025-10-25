import json
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import aiofiles
import anyio
from homeassistant.const import CONF_ENABLED
from homeassistant.core import HomeAssistant

from custom_components.supernotify import (
    CONF_ARCHIVE_PATH,
)
from custom_components.supernotify.archive import ArchivableObject, NotificationArchive
from custom_components.supernotify.notify import SuperNotificationAction


class ArchiveCrashDummy(ArchivableObject):
    def contents(self, minimal: bool = False) -> Any:
        return {"a_dict": {}, "a_list": [], "a_str": "", "a_int": 984}

    def base_filename(self) -> str:
        return "testing"


async def test_integration_archive(mock_hass: HomeAssistant) -> None:
    with tempfile.TemporaryDirectory() as archive:
        uut = SuperNotificationAction(
            mock_hass,
            recipients=[],  # recipients will generate mock person_config data and break json
            archive={CONF_ENABLED: True, CONF_ARCHIVE_PATH: archive},
        )
        await uut.initialize()
        await uut.async_send_message("just a test", target="person.bob")
        assert uut.last_notification is not None
        obj_path: anyio.Path = anyio.Path(archive) / f"{uut.last_notification.base_filename()}.json"
        assert await obj_path.exists()
        async with aiofiles.open(obj_path) as stream:
            blob: str = "".join(await stream.readlines())
            reobj = json.loads(blob)
        assert reobj["_message"] == "just a test"
        assert reobj["target"] == ["person.bob"]
        assert reobj["delivered_envelopes"] == uut.last_notification.delivered_envelopes


async def test__archive() -> None:
    with tempfile.TemporaryDirectory() as archive:
        uut = NotificationArchive(True, archive, "7")
        uut.initialize()
        msg = ArchiveCrashDummy()
        assert uut.archive(msg)

        obj_path: anyio.Path = anyio.Path(archive).joinpath(f"{msg.base_filename()}.json")
        assert await obj_path.exists()
        async with aiofiles.open(obj_path) as stream:
            blob: str = "".join(await stream.readlines())
            reobj = json.loads(blob)
        assert reobj["a_int"] == 984


async def test_cleanup_archive() -> None:
    archive = "config/archive/test"
    uut = NotificationArchive(True, archive, "7")
    uut.initialize()
    old_time = Mock(return_value=Mock(st_ctime=time.time() - (8 * 24 * 60 * 60)))
    new_time = Mock(return_value=Mock(st_ctime=time.time() - (5 * 24 * 60 * 60)))
    mock_files = [
        Mock(path="abc", stat=new_time),
        Mock(path="def", stat=new_time),
        Mock(path="xyz", stat=old_time),
    ]
    with patch("aiofiles.os.scandir", return_value=mock_files) as _scan:
        with patch("aiofiles.os.unlink") as rmfr:
            await uut.cleanup()
            rmfr.assert_called_once_with(Path("xyz"))
    # skip cleanup for a few hours
    first_purge = uut.last_purge
    await uut.cleanup()
    assert first_purge == uut.last_purge


async def test_archive_size() -> None:
    with tempfile.TemporaryDirectory() as tmp_path:
        uut = NotificationArchive(True, tmp_path, "7")
        uut.initialize()
        assert uut.enabled
        assert await uut.size() == 0
        async with aiofiles.open(Path(tmp_path) / "test.foo", mode="w") as f:
            await f.write("{}")
        assert await uut.size() == 1
