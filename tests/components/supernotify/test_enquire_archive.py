"""Tests for supernotify.enquire_archive."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import threading
from typing import TYPE_CHECKING, TextIO
from unittest.mock import patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.archive import _filename_period

from .hass_setup_lib import assert_json_round_trip

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _write_archive_entry(
    directory: pathlib.Path, notification_id: str, created: dt.datetime, outcome: str = "SUCCESS"
) -> pathlib.Path:
    """Write a minimal archived notification JSON file."""
    timestamp = created.isoformat()[:16].replace(":", "-")
    filename = f"{timestamp}_{notification_id}.json"
    payload = {
        "id": notification_id,
        "outcome": outcome,
        "created": created.isoformat(),
        "message": f"Test message for {notification_id}",
        "priority": "medium",
        "delivered": ["testing"],
        "failed": [],
        "suppressed": [],
        "skipped": [],
    }
    path = directory / filename
    path.write_text(json.dumps(payload))
    return path


async def _setup(hass: HomeAssistant, archive_path: str) -> None:
    config = {
        "delivery": {
            "testing": {
                "transport": "generic",
                "target": ["testy.testy"],
                "action": "notify.send_message",
                "inclusion": ["default"],
            }
        },
        "archive": {"enabled": True, "file_path": archive_path},
    }
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()


async def test_enquire_archive_no_archive_configured(hass: HomeAssistant) -> None:
    """enquire_archive raises when no archive is configured."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "delivery": {
                    "testing": {
                        "transport": "generic",
                        "target": ["t"],
                        "action": "notify.send_message",
                        "inclusion": ["default"],
                    }
                }
            }
        },
    )
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(DOMAIN, "enquire_archive", {}, blocking=True, return_response=True)
    assert exc_info.value.translation_key == "no_archive_configured"


async def test_enquire_archive_empty(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """enquire_archive returns an empty list when the archive directory is empty."""
    await _setup(hass, str(tmp_path))
    response = await hass.services.async_call(DOMAIN, "enquire_archive", {}, blocking=True, return_response=True)
    assert response is not None
    assert response["count"] == 0
    assert response["notifications"] == []
    assert_json_round_trip(response, label="enquire_archive_empty")


async def test_enquire_archive_list(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """enquire_archive returns all entries, newest first."""
    base = dt.datetime(2026, 9, 24, 10, 0, tzinfo=dt.UTC)
    for i, nid in enumerate(["aaa", "bbb", "ccc"]):
        _write_archive_entry(tmp_path, nid, base + dt.timedelta(minutes=i))

    await _setup(hass, str(tmp_path))
    response = await hass.services.async_call(DOMAIN, "enquire_archive", {}, blocking=True, return_response=True)
    assert response["count"] == 3
    assert [e["id"] for e in response["notifications"]] == ["ccc", "bbb", "aaa"]
    assert_json_round_trip(response, label="enquire_archive_list")


async def test_enquire_archive_limit(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """enquire_archive respects the limit parameter."""
    base = dt.datetime(2026, 9, 24, 10, 0, tzinfo=dt.UTC)
    for i in range(5):
        _write_archive_entry(tmp_path, f"n{i:02d}", base + dt.timedelta(minutes=i))

    await _setup(hass, str(tmp_path))
    response = await hass.services.async_call(DOMAIN, "enquire_archive", {"limit": 2}, blocking=True, return_response=True)
    assert response["count"] == 2


async def test_enquire_archive_outcome_filter(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """enquire_archive filters by outcome."""
    base = dt.datetime(2026, 9, 24, 10, 0, tzinfo=dt.UTC)
    _write_archive_entry(tmp_path, "ok1", base, outcome="SUCCESS")
    _write_archive_entry(tmp_path, "er1", base + dt.timedelta(minutes=1), outcome="ERROR")
    _write_archive_entry(tmp_path, "ok2", base + dt.timedelta(minutes=2), outcome="SUCCESS")

    await _setup(hass, str(tmp_path))
    response = await hass.services.async_call(
        DOMAIN, "enquire_archive", {"outcome": "SUCCESS"}, blocking=True, return_response=True
    )
    assert response["count"] == 2
    assert all(e["outcome"] == "SUCCESS" for e in response["notifications"])


async def test_enquire_archive_outcome_filter_real_case(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """Archive files hold the DeliveryOutcome value in lower case, the selector offers upper case
    - the filter matches either way (#242)."""
    base = dt.datetime(2026, 9, 24, 10, 0, tzinfo=dt.UTC)
    _write_archive_entry(tmp_path, "ok1", base, outcome="success")
    _write_archive_entry(tmp_path, "er1", base + dt.timedelta(minutes=1), outcome="error")
    _write_archive_entry(tmp_path, "pd1", base + dt.timedelta(minutes=2), outcome="partial_delivery")

    await _setup(hass, str(tmp_path))
    for selector_value, expected in (("ERROR", ["er1"]), ("PARTIAL_DELIVERY", ["pd1"]), ("success", ["ok1"])):
        response = await hass.services.async_call(
            DOMAIN, "enquire_archive", {"outcome": selector_value}, blocking=True, return_response=True
        )
        assert [e["id"] for e in response["notifications"]] == expected


async def test_enquire_archive_by_id(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """enquire_archive with id returns a single notification's full detail."""
    base = dt.datetime(2026, 9, 24, 10, 0, tzinfo=dt.UTC)
    _write_archive_entry(tmp_path, "target-id", base)
    _write_archive_entry(tmp_path, "other-id", base + dt.timedelta(minutes=1))

    await _setup(hass, str(tmp_path))
    response = await hass.services.async_call(
        DOMAIN, "enquire_archive", {"id": "target-id"}, blocking=True, return_response=True
    )
    assert response is not None
    assert response["id"] == "target-id"
    assert "notifications" not in response
    assert_json_round_trip(response, label="enquire_archive_by_id")


async def test_enquire_archive_id_not_found(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """enquire_archive raises when the requested id does not exist."""
    await _setup(hass, str(tmp_path))
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(DOMAIN, "enquire_archive", {"id": "does-not-exist"}, blocking=True, return_response=True)
    assert exc_info.value.translation_key == "archive_entry_not_found"
    assert exc_info.value.translation_placeholders == {"notification_id": "does-not-exist"}
    assert "does-not-exist" in str(exc_info.value)


async def test_enquire_archive_verbosity(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """A list is standard unless asked otherwise, with the debug trace only at full verbosity."""
    path = _write_archive_entry(tmp_path, "dbg", dt_util.now())
    payload = json.loads(path.read_text())
    payload["debug_trace"] = {"delivery_selection": {"ranked": ["testing"]}}
    payload["deliveries"] = {"testing": {"success": [{"target": {"person_id": ["person.unknown"]}}]}}
    path.write_text(json.dumps(payload))

    await _setup(hass, str(tmp_path))

    async def enquire(**data: str) -> dict:
        response = await hass.services.async_call(DOMAIN, "enquire_archive", data, blocking=True, return_response=True)
        assert_json_round_trip(response, label="enquire_archive_verbosity")
        return response

    standard = (await enquire())["notifications"][0]
    assert "debug_trace" not in standard
    assert standard["delivered"] == ["testing"]
    assert (await enquire(verbosity="standard"))["notifications"] == [standard]

    assert (await enquire(verbosity="full"))["notifications"] == [payload]

    summary = (await enquire(verbosity="summary"))["notifications"][0]
    assert summary["id"] == "dbg"
    assert summary["deliveries"] == {"testing": {"success": 1, "recipients": ["person.unknown"]}}
    assert "delivered" not in summary

    # a single notification is in full unless asked otherwise
    assert await enquire(id="dbg") == payload
    assert "debug_trace" not in await enquire(id="dbg", verbosity="standard")
    assert (await enquire(id="dbg", verbosity="summary"))["deliveries"] == summary["deliveries"]

    with pytest.raises(vol.Invalid):
        await enquire(verbosity="chatty")


async def test_enquire_archive_period(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """A period selects the notifications created in a length of time ending now."""
    now = dt_util.now()
    _write_archive_entry(tmp_path, "mins", now - dt.timedelta(minutes=10))
    _write_archive_entry(tmp_path, "hours", now - dt.timedelta(hours=5))
    _write_archive_entry(tmp_path, "days", now - dt.timedelta(days=3))

    await _setup(hass, str(tmp_path))

    async def ids(**data: str) -> set[str]:
        response = await hass.services.async_call(DOMAIN, "enquire_archive", data, blocking=True, return_response=True)
        return {e["id"] for e in response["notifications"]}

    assert await ids(period="last_hour") == {"mins"}
    assert await ids(period="last_12_hours") == {"mins", "hours"}
    assert await ids(period="last_week") == {"mins", "hours", "days"}
    # an explicit start time is used in preference to the period
    assert await ids(period="last_hour", after=(now - dt.timedelta(days=1)).isoformat()) == {"mins", "hours"}
    # a start time with no time zone is local time
    assert await ids(after=(now - dt.timedelta(days=1)).replace(tzinfo=None).isoformat()) == {"mins", "hours"}
    assert await ids(period="last_week", before=(now - dt.timedelta(hours=1)).isoformat()) == {"hours", "days"}

    with pytest.raises(vol.Invalid):
        await ids(period="last_century")


async def test_enquire_archive_only_opens_files_in_range(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """Files named for a time outside `after` and `before` are never opened."""
    now = dt_util.now()
    for name, age in (("new", 0), ("recent", 2), ("wanted", 5), ("old", 9), ("ancient", 72)):
        _write_archive_entry(tmp_path, name, now - dt.timedelta(hours=age))
    (tmp_path / "unconventional.json").write_text(json.dumps({"id": "odd", "created": now.isoformat()}))

    await _setup(hass, str(tmp_path))

    # the scan runs in the executor with the builtin open
    with patch("custom_components.supernotify.archive.open", wraps=open, create=True) as tracked_open:
        response = await hass.services.async_call(
            DOMAIN,
            "enquire_archive",
            {"after": (now - dt.timedelta(hours=6)).isoformat(), "before": (now - dt.timedelta(hours=4)).isoformat()},
            blocking=True,
            return_response=True,
        )
    opened = [pathlib.Path(call.args[0]).name.rpartition("_")[2] for call in tracked_open.call_args_list]
    assert [e["id"] for e in response["notifications"]] == ["wanted"]
    # a file not named for its creation time can't be ruled out without reading it
    assert sorted(opened) == ["unconventional.json", "wanted.json"]


async def test_enquire_archive_reads_files_off_the_event_loop(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    """The scan runs as one job in Home Assistant's executor, never opening a file on the event loop."""
    now = dt_util.now()
    for name, age in (("one", 1), ("two", 2), ("three", 3)):
        _write_archive_entry(tmp_path, name, now - dt.timedelta(hours=age))
    await _setup(hass, str(tmp_path))

    threads: list[int] = []

    def tracked(path: str, encoding: str) -> TextIO:
        threads.append(threading.get_ident())
        return open(path, encoding=encoding)

    with patch("custom_components.supernotify.archive.open", side_effect=tracked, create=True):
        response = await hass.services.async_call(DOMAIN, "enquire_archive", {"limit": 10}, blocking=True, return_response=True)
    assert sorted(e["id"] for e in response["notifications"]) == ["one", "three", "two"]
    assert threads
    assert hass.loop_thread_id not in threads


@pytest.mark.parametrize("time_zone", ["Europe/London", "UTC", "Asia/Kolkata"])
async def test_filename_period_covers_creation_time(hass: HomeAssistant, time_zone: str) -> None:
    """Both sides of a clock change are allowed for, since the file name has no UTC offset."""
    await hass.config.async_set_time_zone(time_zone)
    zone = dt_util.get_default_time_zone()
    # either side of, and both passes through, the hour repeated when UK clocks go back
    for utc in ("2026-10-24T23:30:40", "2026-10-25T00:30:40", "2026-10-25T01:30:40", "2026-03-29T01:30:40"):
        created = dt.datetime.fromisoformat(utc).replace(tzinfo=dt.UTC).astimezone(zone)
        period = _filename_period(f"{created.isoformat()[:16].replace(':', '-')}_abc.json")
        assert period is not None
        assert period[0] <= created.timestamp() <= period[1]
        assert period[1] - period[0] <= 3660
    assert _filename_period(".startup") is None
    assert _filename_period("unconventional.json") is None
