"""End to end flows through the archive, on a real Home Assistant: a notification archived to file
and as an event, then found with enquire_archive and removed with purge_archive"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.core import Event, SupportsResponse
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.compat import vol

if TYPE_CHECKING:
    import pathlib

    from homeassistant.core import HomeAssistant

    from conftest import DummyNotificationService


async def archiving(hass: HomeAssistant, tmp_path: pathlib.Path, event_selection: str) -> list[Event[Any]]:
    # archiving is set in the options flow, which stores the outcomes as names
    archive = {"enabled": True, "file_path": str(tmp_path), "event_selection": event_selection}
    MockConfigEntry(domain=DOMAIN, data={}, options={"archive": archive}).add_to_hass(hass)
    config = {"delivery": {"dummy": {"transport": "generic", "action": "notify.dummy", "inclusion": ["default"]}}}
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
    await hass.async_block_till_done()
    events: list[Event[Any]] = []
    hass.bus.async_listen("supernotification", events.append)
    return events


async def enquire(hass: HomeAssistant, action: str, **data: Any) -> dict[str, Any]:
    response = await hass.services.async_call(DOMAIN, action, data, blocking=True, return_response=SupportsResponse.ONLY)
    assert response is not None
    return dict(response)


async def test_notification_archived_found_and_purged(
    hass: HomeAssistant, dummy_notify: DummyNotificationService, tmp_path: pathlib.Path
) -> None:
    events = await archiving(hass, tmp_path, "SUCCESS")

    await hass.services.async_call(DOMAIN, "notify", {"message": "Door open", "priority": "high"}, blocking=True)
    await hass.async_block_till_done()

    assert len(dummy_notify.calls) == 1
    found = await enquire(hass, "enquire_archive", outcome="success", priority=["high"], verbosity="summary")
    assert found["count"] == 1
    (summary,) = found["notifications"]
    assert summary["message"] == "Door open"
    assert summary["deliveries"]["dummy"] == {"success": 1}
    assert (await enquire(hass, "enquire_archive", id=summary["id"]))["message"] == "Door open"

    (event,) = events
    assert event.data["id"] == summary["id"]

    purged = await enquire(hass, "purge_archive", days=0)
    assert purged == {"purged": 1, "remaining": 0, "days": 0}
    assert (await enquire(hass, "enquire_archive"))["count"] == 0


async def test_no_event_for_unselected_outcome(
    hass: HomeAssistant, dummy_notify: DummyNotificationService, tmp_path: pathlib.Path
) -> None:
    events = await archiving(hass, tmp_path, "ERROR")

    await hass.services.async_call(DOMAIN, "notify", {"message": "Door open"}, blocking=True)
    await hass.async_block_till_done()

    assert len(dummy_notify.calls) == 1
    assert (await enquire(hass, "enquire_archive"))["count"] == 1
    assert events == []


async def test_enquire_archive_rejects_invalid_date(
    hass: HomeAssistant, dummy_notify: DummyNotificationService, tmp_path: pathlib.Path
) -> None:
    await archiving(hass, tmp_path, "NONE")
    # rejected by the action's schema, before any search, rather than as an unexpected error
    with pytest.raises(vol.Invalid):
        await enquire(hass, "enquire_archive", after="last tuesday")
