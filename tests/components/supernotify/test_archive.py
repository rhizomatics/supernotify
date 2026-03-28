import json
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import aiofiles
import anyio
import pytest
from homeassistant.const import CONF_ENABLED

from custom_components.supernotify.archive import ArchivableObject, NotificationArchive
from custom_components.supernotify.const import (
    CONF_ARCHIVE_DAYS,
    CONF_ARCHIVE_DIAGNOSTICS,
    CONF_ARCHIVE_MQTT_QOS,
    CONF_ARCHIVE_MQTT_RETAIN,
    CONF_ARCHIVE_MQTT_TOPIC,
    CONF_ARCHIVE_PATH,
)
from custom_components.supernotify.notify import SupernotifyAction
from custom_components.supernotify.schema import SCENARIO_SCHEMA, OutcomeSelection

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.hass_api import HomeAssistantAPI


class ArchiveCrashDummy(ArchivableObject):
    def contents(self, diagnostics: bool = False, **_kwargs: Any) -> Any:
        return {"a_dict": {}, "a_list": [], "a_str": "", "a_int": 984}

    def base_filename(self) -> str:
        return "testing"


@pytest.mark.parametrize(
    argnames="diagnostics",
    argvalues=[OutcomeSelection.NONE, OutcomeSelection.ALL],
    ids=["normal", "trace"],
)
async def test_integration_archive(mock_hass: HomeAssistant, diagnostics: OutcomeSelection) -> None:
    with tempfile.TemporaryDirectory() as archive:
        uut = SupernotifyAction(
            mock_hass,
            scenarios={
                "critical": SCENARIO_SCHEMA({
                    "conditions": "{{notification_priority in ['critical']}}",
                }),
                "alarming": SCENARIO_SCHEMA({"delivery": {"chime": {"enabled": True}}}),
            },
            deliveries={"chime": {"transport": "chime"}},
            recipients=[],  # recipients will generate mock person_config data and break json
            archive={CONF_ENABLED: True, CONF_ARCHIVE_PATH: archive, CONF_ARCHIVE_DIAGNOSTICS: diagnostics},
        )
        await uut.initialize()
        await uut.async_send_message(
            "just a test", target="person.bob", data={"priority": "critical", "apply_scenarios": ["alarming"]}
        )

        assert uut.last_notification is not None
        obj_path: anyio.Path = anyio.Path(archive) / f"{uut.last_notification.base_filename()}.json"
        assert await obj_path.exists()
        async with aiofiles.open(obj_path) as stream:
            blob: str = "".join(await stream.readlines())
            reobj = json.loads(blob)
        assert reobj["priority"] == "critical"
        for outcome in ("delivered", "failed", "skipped", "no_envelopes"):
            for delivery_name in uut.last_notification.deliveries:
                assert len(reobj["deliveries"][delivery_name].get(outcome, [])) == len(
                    uut.last_notification.deliveries[delivery_name].get(outcome, [])
                )

        if diagnostics == OutcomeSelection.NONE:
            assert reobj["enabled_scenarios"] == ["alarming", "critical"]
        else:
            assert reobj["enabled_scenarios"]["alarming"]["enabled"]


async def test_file_archive(hass_api: HomeAssistantAPI) -> None:
    with tempfile.TemporaryDirectory() as archive:
        uut = NotificationArchive({CONF_ENABLED: True, CONF_ARCHIVE_PATH: archive, CONF_ARCHIVE_DAYS: "7"}, hass_api)
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


def test_event_archiver_specific_diagnostic_flags(mock_hass_api: HomeAssistantAPI) -> None:
    from custom_components.supernotify.archive import EventArchiver

    # Lines 85, 90, 92, 98: each flag triggers its own log in else branch
    flags = OutcomeSelection.SUCCESS | OutcomeSelection.FALLBACK_DELIVERY | OutcomeSelection.NO_DELIVERY | OutcomeSelection.DUPE
    archiver = EventArchiver(mock_hass_api, "test.event", flags)
    assert archiver.diagnostics == flags


async def test_archive_directory_init_path_not_creatable() -> None:
    from custom_components.supernotify.archive import ArchiveDirectory

    with (
        patch.object(anyio.Path, "exists", new=AsyncMock(return_value=False)),
        patch.object(anyio.Path, "mkdir", new=AsyncMock(side_effect=PermissionError("no permission"))),
    ):
        uut = ArchiveDirectory("/no/permission/path", 60)
        await uut.initialize()
        assert not uut.enabled


async def test_archive_directory_cleanup_no_path() -> None:
    from custom_components.supernotify.archive import ArchiveDirectory

    uut = ArchiveDirectory("/some/path", 60)
    # skip initialize so archive_path stays None
    result = await uut.cleanup(1, True)
    assert result == 0


async def test_archive_directory_cleanup_skips_startup(mock_hass_api: HomeAssistantAPI) -> None:
    import time
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    from custom_components.supernotify.archive import ArchiveDirectory

    with tempfile.TemporaryDirectory() as tmp:
        uut = ArchiveDirectory(tmp, 60)
        await uut.initialize()
        old_time = MagicMock(return_value=MagicMock(st_ctime=time.time() - (8 * 24 * 60 * 60)))
        startup_entry = MagicMock()
        startup_entry.name = ".startup"
        startup_entry.stat = old_time
        old_entry = MagicMock()
        old_entry.name = "old_file.json"
        old_entry.path = str(Path(tmp) / "old_file.json")
        old_entry.stat = old_time
        with patch("aiofiles.os.scandir", return_value=[startup_entry, old_entry]):
            with patch("aiofiles.os.unlink") as mock_unlink:
                purged = await uut.cleanup(1, True)
        assert purged == 1  # startup skipped, old_file purged
        mock_unlink.assert_called_once()
