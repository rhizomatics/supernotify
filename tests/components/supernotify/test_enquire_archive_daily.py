"""Tests for enquire_archive with verbosity: daily - counts per local day instead of notifications."""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.archive import summarize_by_day

from .test_enquire_archive import _setup

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant

ROME = ZoneInfo("Europe/Rome")


@pytest.fixture
def rome() -> Iterator[None]:
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(ROME)
    yield
    dt_util.set_default_time_zone(previous)


def _entry(
    created: dt.datetime,
    outcome: str = "success",
    priority: str = "medium",
    deliveries: dict[str, Any] | None = None,
    scenarios: Any = None,  # noqa: ANN401 - a list, or a mapping by name in older files
) -> dict[str, Any]:
    return {
        "id": created.isoformat(),
        "created": created.isoformat(),
        "outcome": outcome,
        "priority": priority,
        "deliveries": deliveries if deliveries is not None else {"push": {"success": [{"target": {}}]}},
        "enabled_scenarios": scenarios if scenarios is not None else [],
    }


def test_counts_per_local_day(rome: None) -> None:
    # 23:30 UTC on the 3rd is already the 4th in Rome
    entries = [
        _entry(dt.datetime(2026, 10, 3, 8, 0, tzinfo=ROME), scenarios=["morning", "home"]),
        _entry(dt.datetime(2026, 10, 3, 23, 30, tzinfo=dt.UTC), priority="high", scenarios=["night"]),
        _entry(
            dt.datetime(2026, 10, 4, 9, 15, tzinfo=ROME),
            outcome="partial_delivery",
            deliveries={"push": {"success": [{}]}, "alexa": {"error": [{}]}, "email": {"skipped": {"suppression_reason": "X"}}},
            scenarios=["morning"],
        ),
        _entry(dt.datetime(2026, 10, 4, 9, 20, tzinfo=ROME), outcome="DUPE", deliveries={}),
    ]

    result = summarize_by_day(entries)

    assert result["count"] == 4
    assert [day["date"] for day in result["days"]] == ["2026-10-03", "2026-10-04"]
    oct3, oct4 = result["days"]
    assert oct3["count"] == 1
    assert oct3["hour"][8] == 1
    assert oct3["scenarios"] == {"morning": 1, "home": 1}
    assert oct4["count"] == 3
    assert oct4["hour"][1] == 1  # 23:30 UTC = 01:30 in Rome
    assert oct4["hour"][9] == 2
    assert oct4["outcome"] == {"success": 1, "partial_delivery": 1, "dupe": 1}
    assert oct4["priority"] == {"high": 1, "medium": 2}
    assert oct4["deliveries"] == {"push": {"success": 2, "failed": 0}, "alexa": {"success": 0, "failed": 1}}
    assert oct4["scenarios"] == {"night": 1, "morning": 1}


def test_older_files_with_scenarios_by_name(rome: None) -> None:
    entries = [
        _entry(dt.datetime(2026, 9, 25, 15, 51, tzinfo=ROME), scenarios={"multi_home": {"name": "multi_home"}, "afternoon": {}})
    ]

    assert summarize_by_day(entries)["days"][0]["scenarios"] == {"multi_home": 1, "afternoon": 1}


def test_a_day_crossing_daylight_saving_is_one_day(rome: None) -> None:
    # 25 October 2026: clocks go back at 03:00 in Rome, so the day has 25 hours
    start = dt.datetime(2026, 10, 24, 22, 30, tzinfo=dt.UTC)  # 00:30 local, CEST
    entries = [_entry(start + dt.timedelta(hours=h)) for h in range(25)]

    days = summarize_by_day(entries)["days"]

    assert [day["date"] for day in days] == ["2026-10-25"]
    assert days[0]["count"] == 25
    assert days[0]["hour"][2] == 2  # 02:xx happens twice


def test_unreadable_created_and_odd_values_are_skipped(rome: None) -> None:
    entries = [
        {"created": "not a date"},
        {"outcome": "success"},
        {"created": "2026-10-04T10:00:00+02:00", "deliveries": {"push": "?"}, "enabled_scenarios": "solo"},
    ]

    result = summarize_by_day(entries)

    assert result["count"] == 1
    day = result["days"][0]
    assert day["outcome"] == {"unknown": 1}
    assert day["priority"] == {"unknown": 1}
    assert day["deliveries"] == {}
    assert day["scenarios"] == {"solo": 1}


def test_empty() -> None:
    assert summarize_by_day([]) == {"days": [], "count": 0}


def _write(directory: pathlib.Path, created: dt.datetime, notification_id: str | None = None) -> None:
    entry = _entry(created)
    entry["id"] = notification_id or f"n{created.timestamp():.0f}"
    name = created.isoformat()[:16].replace(":", "-") + f"_{entry['id']}.json"
    (directory / name).write_text(json.dumps(entry))


async def _daily(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    response = await hass.services.async_call(
        DOMAIN, "enquire_archive", {"verbosity": "daily", **data}, blocking=True, return_response=True
    )
    assert response is not None
    return dict(response)


async def test_action_counts_every_notification_without_a_limit(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    await hass.config.async_set_time_zone("Europe/Rome")
    now = dt_util.now()
    for i in range(30):
        _write(tmp_path, now - dt.timedelta(hours=i * 3))
    await _setup(hass, str(tmp_path))

    result = await _daily(hass, {})

    assert result["count"] == 30
    assert sum(day["count"] for day in result["days"]) == 30
    assert all("notifications" not in day for day in result["days"])


async def test_action_period_and_limit(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    await hass.config.async_set_time_zone("Europe/Rome")
    now = dt_util.now()
    for i in range(10):
        _write(tmp_path, now - dt.timedelta(days=i, minutes=5))
    await _setup(hass, str(tmp_path))

    assert (await _daily(hass, {"period": "last_week"}))["count"] == 7
    assert (await _daily(hass, {"limit": 3}))["count"] == 3


async def test_action_daily_for_one_id(hass: HomeAssistant, tmp_path: pathlib.Path) -> None:
    await hass.config.async_set_time_zone("Europe/Rome")
    created = dt_util.now() - dt.timedelta(minutes=10)
    _write(tmp_path, created, "abc123")
    await _setup(hass, str(tmp_path))

    result = await _daily(hass, {"id": "abc123"})

    assert result["count"] == 1
    assert result["days"][0]["date"] == created.date().isoformat()
