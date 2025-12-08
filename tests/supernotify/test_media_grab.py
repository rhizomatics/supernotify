import io
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import aiofiles
import anyio
import pytest
from homeassistant.const import STATE_HOME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
)
from homeassistant.helpers.entity_component import EntityComponent
from PIL import Image, ImageChops
from pytest_httpserver import BlockingHTTPServer

from conftest import IMAGE_PATH, TestImage
from custom_components.supernotify import PTZ_METHOD_FRIGATE
from custom_components.supernotify.context import Context
from custom_components.supernotify.media_grab import (
    ReprocessOption,
    grab_image,
    move_camera_to_ptz_preset,
    select_avail_camera,
    snap_camera,
    snap_image_entity,
    snapshot_from_url,
)
from custom_components.supernotify.notification import Notification
from tests.supernotify.doubles_lib import MockImageEntity

LOSSY_FORMATS = ["jpeg"]
UNLOSSY_FORMATS = ["png", "gif"]


@pytest.mark.enable_socket
async def test_snapshot_url_with_abs_path(
    hass: HomeAssistant, local_server: BlockingHTTPServer, sample_image: TestImage, tmp_path: Path
) -> None:
    media_path: Path = tmp_path / "media"

    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(sample_image.contents, content_type=sample_image.mime_type)  # type: ignore
    retrieved_image_path = await snapshot_from_url(hass, snapshot_url, "notify-uuid-1", anyio.Path(media_path), None)

    assert retrieved_image_path is not None
    retrieved_image = Image.open(retrieved_image_path)
    original_image = Image.open(sample_image.path)
    assert retrieved_image.size == original_image.size
    if sample_image.ext in UNLOSSY_FORMATS:
        diff = ImageChops.difference(retrieved_image, original_image)
        assert diff.getbbox() is None


@pytest.mark.enable_socket
async def test_snapshot_url_with_opts(
    hass: HomeAssistant, local_server: BlockingHTTPServer, sample_image: TestImage, tmp_path: Path
) -> None:
    media_path: Path = tmp_path / "media"

    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(sample_image.contents, content_type=sample_image.mime_type)  # type: ignore
    retrieved_image_path: Path | None = await snapshot_from_url(
        hass,
        snapshot_url,
        "notify-uuid-1",
        anyio.Path(media_path),
        None,
        jpeg_opts={"quality": 30, "progressive": True, "optimize": True, "comment": "changed by test"},
        png_opts={"quality": 30, "dpi": (60, 90), "optimize": True, "comment": "changed by test"},
    )
    assert retrieved_image_path is not None

    retrieved_image: Image.Image = Image.open(str(retrieved_image_path))
    original_image: Image.Image = Image.open(str(sample_image.path))
    assert retrieved_image.size == original_image.size
    if sample_image.ext == "jpeg":
        assert retrieved_image.info.get("comment") == b"changed by test"
        assert retrieved_image.info.get("progressive") == 1
    elif sample_image.ext == "png":
        assert retrieved_image.info.get("dpi") == pytest.approx((60, 90), rel=1e-4)
    else:
        assert retrieved_image.info.get("comment") is None


async def test_snapshot_url_with_broken_url(hass: HomeAssistant, tmp_path: Path) -> None:
    media_path: Path = tmp_path / "media"
    snapshot_url = "http://no-such-domain.local:9494/snapshot_image_hass"
    retrieved_image_path = await snapshot_from_url(hass, snapshot_url, "notify-uuid-1", anyio.Path(media_path), None)
    assert retrieved_image_path is None


@pytest.mark.parametrize(
    argnames="reprocess", argvalues=[ReprocessOption.ALWAYS, ReprocessOption.NEVER, ReprocessOption.PRESERVE]
)
async def test_snap_camera(hass, reprocess: ReprocessOption, tmp_path: Path) -> None:
    called_entity: str | None = None
    fixture_image_path: Path = IMAGE_PATH / "example_image.jpeg"

    async def dummy_snapshot(call: ServiceCall, **kwargs) -> ServiceResponse | None:
        nonlocal called_entity
        called_entity = call.data["entity_id"]
        async with await anyio.Path(fixture_image_path).open("rb") as f:
            image = Image.open(io.BytesIO(await f.read()))
            buffer = BytesIO()
            image.save(buffer, "jpeg", comment="Original Comment")
        async with aiofiles.open(call.data["filename"], "wb") as file:
            await file.write(buffer.getbuffer())
        return None

    hass.services.async_register("camera", "snapshot", dummy_snapshot)
    jpeg_opts = {"progressive": True, "optimize": True, "comment": "xunit cam woz here"}
    if reprocess == ReprocessOption.PRESERVE:
        del jpeg_opts["comment"]

    image_path: Path | None = await snap_camera(
        hass,
        "camera.xunit",
        "notify-uuid-1",
        media_path=anyio.Path(tmp_path),
        max_camera_wait=1,
        reprocess=reprocess,
        jpeg_opts=jpeg_opts,
    )
    assert called_entity == "camera.xunit"
    assert image_path is not None
    reprocessed_image: Image.Image = Image.open(str(image_path))
    if reprocess == ReprocessOption.NEVER:
        assert reprocessed_image.info.get("comment") == b"Original Comment"
        assert reprocessed_image.info.get("progressive") is None
    elif reprocess == ReprocessOption.ALWAYS:
        assert reprocessed_image.info.get("comment") == b"xunit cam woz here"
        assert reprocessed_image.info.get("progressive") == 1
    elif reprocess == ReprocessOption.PRESERVE:
        assert reprocessed_image.info.get("comment") == b"Original Comment"
        assert reprocessed_image.info.get("progressive") == 1


async def test_snap_image_entity(mock_context: Context, sample_image: TestImage, tmp_path: Path) -> None:

    image_entity = MockImageEntity(sample_image.path)
    if mock_context.hass_api._hass:
        mock_context.hass_api._hass.data["image"] = Mock(spec=EntityComponent)
        mock_context.hass_api._hass.data["image"].get_entity = Mock(return_value=image_entity)

    snap_image_path = await snap_image_entity(
        mock_context, "image.testing", media_path=anyio.Path(tmp_path), notification_id="notify_001"
    )
    assert snap_image_path is not None
    retrieved_image = Image.open(snap_image_path)

    original_image = Image.open(sample_image.path)
    assert "exif" not in retrieved_image.info
    assert retrieved_image.size == original_image.size
    if sample_image.ext in UNLOSSY_FORMATS:
        diff = ImageChops.difference(retrieved_image, original_image)
        assert diff.getbbox() is None


async def test_grab_image(mock_context: Context, sample_image: TestImage, local_server: BlockingHTTPServer) -> None:
    notification = Notification(mock_context, "Test Me 123")
    result: Path | None = await grab_image(notification, "mail", mock_context)
    assert result is None

    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(sample_image.contents, content_type=sample_image.mime_type)  # type: ignore

    notification = Notification(mock_context, "Test Me 123", action_data={"media": {"snapshot_url": snapshot_url}})
    result = await grab_image(notification, "mail", mock_context)
    assert result is not None
    retrieved_image = Image.open(result)
    assert retrieved_image is not None  # images tested by lower funcs


async def test_move_camera_onvif(mock_hass) -> None:
    await move_camera_to_ptz_preset(mock_hass, "camera.xunit", preset="Upstairs")
    mock_hass.services.async_call.assert_awaited_once_with(
        "onvif", "ptz", service_data={"move_mode": "GotoPreset", "preset": "Upstairs"}, target={"entity_id": "camera.xunit"}
    )


async def test_move_camera_frigate(mock_hass) -> None:
    await move_camera_to_ptz_preset(mock_hass, "camera.xunit", preset="Upstairs", method=PTZ_METHOD_FRIGATE)
    mock_hass.services.async_call.assert_awaited_once_with(
        "frigate", "ptz", service_data={"action": "preset", "argument": "Upstairs"}, target={"entity_id": "camera.xunit"}
    )


def valid_state(home_entities: list, not_home_entities: list) -> Callable:
    def checker(entity, state) -> bool:
        if entity in home_entities and state == STATE_HOME:
            return True
        if entity in not_home_entities and state == STATE_HOME:
            return False
        raise ValueError("Test values not as expected")

    return checker


def test_select_camera_not_in_config(mock_hass) -> None:
    assert select_avail_camera(mock_hass, {}, "camera.unconfigured") == "camera.unconfigured"


def test_select_untracked_primary_camera(mock_hass) -> None:
    assert (
        select_avail_camera(mock_hass, {"camera.untracked": {"alias": "Test Untracked"}}, "camera.untracked")
        == "camera.untracked"
    )


def test_select_tracked_primary_camera(mock_hass) -> None:
    mock_hass.states.is_state.side_effect = valid_state(["device_tracker.cam1"], [])
    assert (
        select_avail_camera(mock_hass, {"camera.tracked": {"device_tracker": "device_tracker.cam1"}}, "camera.tracked")
        == "camera.tracked"
    )


def test_no_select_unavail_primary_camera(mock_hass) -> None:
    mock_hass.states.is_state.side_effect = valid_state([], ["device_tracker.cam1"])
    assert (
        select_avail_camera(
            mock_hass,
            {"camera.tracked": {"camera": "camera.tracked", "device_tracker": "device_tracker.cam1"}},
            "camera.tracked",
        )
        is None
    )


def test_select_avail_alt_camera(mock_hass) -> None:
    mock_hass.states.is_state.side_effect = valid_state(
        ["device_tracker.altcam2"], ["device_tracker.cam1", "device_tracker.altcam1"]
    )

    assert (
        select_avail_camera(
            mock_hass,
            {
                "camera.tracked": {
                    "camera": "camera.tracked",
                    "device_tracker": "device_tracker.cam1",
                    "alt_camera": ["camera.alt1", "camera.alt2", "camera.alt3"],
                },
                "camera.alt1": {"camera": "camera.alt1", "device_tracker": "device_tracker.altcam1"},
                "camera.alt2": {"camera": "camera.alt2", "device_tracker": "device_tracker.altcam2"},
            },
            "camera.tracked",
        )
        == "camera.alt2"
    )


def test_select_untracked_alt_camera(mock_hass) -> None:
    mock_hass.states.is_state.side_effect = valid_state(
        [], ["device_tracker.cam1", "device_tracker.altcam1", "device_tracker.altcam2"]
    )
    assert (
        select_avail_camera(
            mock_hass,
            {
                "camera.tracked": {
                    "camera": "camera.tracked",
                    "device_tracker": "device_tracker.cam1",
                    "alt_camera": ["camera.alt1", "camera.alt2", "camera.alt3"],
                },
                "camera.alt1": {"camera": "camera.alt1", "device_tracker": "device_tracker.altcam1"},
                "camera.alt2": {"camera": "camera.alt2", "device_tracker": "device_tracker.altcam2"},
            },
            "camera.tracked",
        )
        == "camera.alt3"
    )
