import json
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiofiles
import anyio
from homeassistant.const import CONF_ENABLED
from homeassistant.core import HomeAssistant

from custom_components.supernotify import (
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
)
from custom_components.supernotify.archive import ArchivableObject, NotificationArchive
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.notify import SupernotifyAction


class ArchiveCrashDummy(ArchivableObject):
    def contents(self, minimal: bool = False,**_kwargs:Any) -> Any:
        return {"a_dict": {}, "a_list": [], "a_str": "", "a_int": 984}

    def base_filename(self) -> str:
        return "testing"


async def test_integration_archive(mock_hass: HomeAssistant) -> None:
    with tempfile.TemporaryDirectory() as archive:
        uut = SupernotifyAction(
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
        assert reobj["priority"] == "medium"
        assert reobj["target"] == {"person_id": ["person.bob"]}
        assert reobj["delivered_envelopes"] == uut.last_notification.delivered_envelopes


async def test_file_archive(mock_hass_api: HomeAssistantAPI) -> None:
    with tempfile.TemporaryDirectory() as archive:
        uut = NotificationArchive({CONF_ENABLED: True, CONF_ARCHIVE_PATH: archive, CONF_ARCHIVE_DAYS: "7"}, mock_hass_api)
        await uut.initialize()
        msg = ArchiveCrashDummy()
        assert await uut.archive(msg)

        obj_path: anyio.Path = anyio.Path(archive).joinpath(f"{msg.base_filename()}.json")
        assert await obj_path.exists()
        async with aiofiles.open(obj_path) as stream:
            blob: str = "".join(await stream.readlines())
            reobj = json.loads(blob)
        assert reobj["a_int"] == 984


async def test_cleanup_archive(mock_hass_api: HomeAssistantAPI) -> None:
    archive = "config/archive/test"
    uut = NotificationArchive({CONF_ENABLED: True, CONF_ARCHIVE_PATH: archive, CONF_ARCHIVE_DAYS: "7"}, mock_hass_api)
    await uut.initialize()
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
    assert uut.archive_directory is not None
    first_purge = uut.archive_directory.last_purge
    await uut.cleanup()
    assert first_purge == uut.archive_directory.last_purge


async def test_archive_size(mock_hass_api: HomeAssistantAPI) -> None:
    with tempfile.TemporaryDirectory() as tmp_path:
        uut = NotificationArchive({CONF_ENABLED: True, CONF_ARCHIVE_PATH: tmp_path, CONF_ARCHIVE_DAYS: "7"}, mock_hass_api)
        await uut.initialize()
        assert uut.enabled
        assert await uut.size() == 0
        async with aiofiles.open(Path(tmp_path) / "test.foo", mode="w") as f:
            await f.write("{}")
        assert await uut.size() == 1


async def test_archive_publish(mock_hass_api: HomeAssistantAPI) -> None:
    uut = NotificationArchive(
        {CONF_ENABLED: True, CONF_ARCHIVE_MQTT_TOPIC: "test.topic", CONF_ARCHIVE_MQTT_QOS: "3", CONF_ARCHIVE_MQTT_RETAIN: True},
        mock_hass_api,
    )

    await uut.initialize()
    msg = ArchiveCrashDummy()
    assert await uut.archive(msg)
    mock_hass_api.mqtt_publish.assert_called_with(  # type: ignore
        topic="test.topic/testing", payload={"a_dict": {}, "a_list": [], "a_str": "", "a_int": 984}, qos=3, retain=True
    )
    mock_hass_api.mqtt_publish.reset_mock()  # type: ignore
    mock_hass_api.mqtt_publish.async_publish.reset_mock()  # type: ignore

    uut = NotificationArchive(
        {CONF_ENABLED: True, CONF_ARCHIVE_MQTT_TOPIC: "test.topic", CONF_ARCHIVE_MQTT_QOS: "3", CONF_ARCHIVE_MQTT_RETAIN: True},
        mock_hass_api,
    )

    mock_hass_api.mqtt_available = AsyncMock(return_value=False)  # type: ignore
    await uut.initialize()
    msg = ArchiveCrashDummy()
    assert await uut.archive(msg) is False
    mock_hass_api.mqtt_publish.assert_not_called()  # type: ignore
