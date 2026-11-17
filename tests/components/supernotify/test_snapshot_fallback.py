"""A list of snapshot URLs tried in turn, then the camera, with a repair at `help_url` when none of the URLs works"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import anyio
import pytest
import voluptuous as vol
from anyio import Path
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from conftest import IMAGE_PATH
from custom_components.supernotify.media_grab import grab_image, snap_notification_image, snapshot_from_url
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import MEDIA_SCHEMA

from .hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pytest_httpserver import HTTPServer

    from custom_components.supernotify.hass_api import HomeAssistantAPI

DELIVERIES = """
mail:
    transport: email
    action: notify.smtp
"""
GIF = "/api/frigate/notifications/abc/event_preview.gif"
JPG = "/api/frigate/notifications/abc/snapshot.jpg?bbox=1"
HELP = "/config/integrations/integration/camera_autonotify"
FIXTURE = anyio.Path(IMAGE_PATH / "example_image.jpeg")


def fake_fetch(results: dict[str, str | None]) -> Callable[..., Awaitable[Path | None]]:
    """A stand-in for snapshot_from_url: the image for a URL mapped to None, else that URL's failure"""
    calls: list[str] = []

    async def fetch(
        _hass_api: HomeAssistantAPI, url: str, *_args: object, failures: list[str] | None = None, **_kwargs: object
    ) -> Path | None:
        calls.append(url)
        reason = results[url]
        if reason is None:
            return FIXTURE
        if failures is not None:
            failures.append(reason)
        return None

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


async def notification_for(hass: HomeAssistant, tmp_aiopath: Path, media: dict[str, Any]) -> Notification:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES, media_path=tmp_aiopath)
    await ctx.test_initialize()
    notification = Notification(ctx, "Test", action_data={"media": media})
    await notification.initialize()
    return notification


def test_schema_accepts_list_of_urls_with_reprocess_and_help_url() -> None:
    media = {"snapshot_url": [{"url": GIF, "reprocess": "never"}, JPG], "help_url": HELP}
    assert MEDIA_SCHEMA(media) == media


def test_schema_still_accepts_single_url() -> None:
    assert MEDIA_SCHEMA({"snapshot_url": JPG}) == {"snapshot_url": JPG}


def test_schema_rejects_bad_reprocess_on_a_url() -> None:
    with pytest.raises(vol.Invalid):
        MEDIA_SCHEMA({"snapshot_url": [{"url": GIF, "reprocess": "sometimes"}]})


async def test_list_leaves_first_url_in_media_for_transports(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    """Transports that pass the URL on to a phone read a single string, as before"""
    urls = [{"url": GIF, "reprocess": "never"}, JPG]
    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": urls})
    assert notification.media["snapshot_url"] == GIF
    assert urls == [{"url": GIF, "reprocess": "never"}, JPG]  # the caller's own list is left alone


async def test_urls_tried_in_turn_until_one_gives_an_image(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": [GIF, JPG]})
    fetch = fake_fetch({GIF: "HTTP 404", JPG: None})
    with patch("custom_components.supernotify.media_grab.snapshot_from_url", side_effect=fetch):
        assert await snap_notification_image(notification, notification.context) == FIXTURE
    assert fetch.calls == [GIF, JPG]
    # later deliveries, such as mobile push, get the URL that worked
    assert notification.media["snapshot_url"] == JPG


async def test_first_url_that_works_stops_the_search(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": [GIF, JPG]})
    fetch = fake_fetch({GIF: None, JPG: None})
    with patch("custom_components.supernotify.media_grab.snapshot_from_url", side_effect=fetch):
        await snap_notification_image(notification, notification.context)
    assert fetch.calls == [GIF]


@pytest.mark.parametrize("snapshot_url", [JPG, [GIF, JPG]])
async def test_camera_snapped_when_no_url_works(hass: HomeAssistant, tmp_aiopath: Path, snapshot_url: str | list[str]) -> None:
    """The camera was ignored whenever there was a snapshot URL, and is now the last resort"""
    notification = await notification_for(
        hass, tmp_aiopath, {"snapshot_url": snapshot_url, "camera_entity_id": "camera.courtyard"}
    )
    fetch = fake_fetch({GIF: "HTTP 404", JPG: "HTTP 500"})
    with (
        patch("custom_components.supernotify.media_grab.snapshot_from_url", side_effect=fetch),
        patch("custom_components.supernotify.media_grab.select_avail_camera", return_value="camera.courtyard"),
        patch("custom_components.supernotify.media_grab.snap_camera", return_value=FIXTURE) as mock_snap,
    ):
        assert await snap_notification_image(notification, notification.context) == FIXTURE
    mock_snap.assert_called_once()


async def test_reprocess_of_the_url_that_worked_is_used(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    """`reprocess: never` on a GIF keeps its frames, without stopping a JPEG fallback being reprocessed"""
    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": [{"url": GIF, "reprocess": "never"}, JPG]})
    with patch("custom_components.supernotify.media_grab.snapshot_from_url", side_effect=fake_fetch({GIF: None})):
        result = await grab_image(notification, notification.context.delivery("mail"), notification.context)
    assert result == FIXTURE  # `never` gives back the image as fetched

    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": [{"url": GIF, "reprocess": "never"}, JPG]})
    with patch(
        "custom_components.supernotify.media_grab.snapshot_from_url", side_effect=fake_fetch({GIF: "HTTP 404", JPG: None})
    ):
        result = await grab_image(notification, notification.context.delivery("mail"), notification.context)
    assert result is not None
    assert result != FIXTURE  # reprocessed into the media path


async def test_repair_at_help_url_when_no_url_works(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": [GIF, JPG], "help_url": HELP})
    fetch = fake_fetch({GIF: "HTTP 404", JPG: "it is not an image"})
    with patch("custom_components.supernotify.media_grab.snapshot_from_url", side_effect=fetch):
        await snap_notification_image(notification, notification.context)

    issues = [i for i in ir.async_get(hass).issues.values() if i.translation_key == "snapshot_unavailable"]
    assert len(issues) == 1
    assert issues[0].learn_more_url == HELP
    assert issues[0].translation_placeholders is not None
    failures = issues[0].translation_placeholders["failures"]
    assert GIF in failures
    assert "HTTP 404" in failures
    assert "it is not an image" in failures

    # resolved once a URL works again
    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": [GIF, JPG], "help_url": HELP})
    with patch("custom_components.supernotify.media_grab.snapshot_from_url", side_effect=fake_fetch({GIF: None})):
        await snap_notification_image(notification, notification.context)
    assert not [i for i in ir.async_get(hass).issues.values() if i.translation_key == "snapshot_unavailable"]


async def test_no_repair_without_help_url(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    notification = await notification_for(hass, tmp_aiopath, {"snapshot_url": [GIF, JPG]})
    with patch(
        "custom_components.supernotify.media_grab.snapshot_from_url",
        side_effect=fake_fetch({GIF: "HTTP 404", JPG: "HTTP 404"}),
    ):
        await snap_notification_image(notification, notification.context)
    assert not [i for i in ir.async_get(hass).issues.values() if i.translation_key == "snapshot_unavailable"]


@pytest.mark.enable_socket
async def test_snapshot_from_url_gives_reason_for_failure(
    unmocked_hass_api: HomeAssistantAPI, local_server: HTTPServer, tmp_aiopath: Path
) -> None:
    local_server.expect_request("/bad").respond_with_data("not found", status=404)
    failures: list[str] = []
    result = await snapshot_from_url(
        unmocked_hass_api, local_server.url_for("/bad"), "n1", tmp_aiopath / "media", None, failures=failures
    )
    assert result is None
    assert failures == ["HTTP 404"]
