"""Tests for supernotify.enquire_archive."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from typing import TYPE_CHECKING

import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN

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
