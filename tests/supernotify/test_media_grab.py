import io
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import pytest
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from PIL import Image, ImageChops
from pytest_httpserver import BlockingHTTPServer

from custom_components.supernotify import PTZ_METHOD_FRIGATE
from custom_components.supernotify.context import Context
from custom_components.supernotify.media_grab import (
    move_camera_to_ptz_preset,
    select_avail_camera,
    snap_camera,
    snap_image,
    snapshot_from_url,
)
from tests.supernotify.doubles_lib import MockImageEntity

IMAGE_PATH: Path = Path("tests") / "supernotify" / "fixtures" / "media"
LOSSY_FORMATS = ["jpeg"]
UNLOSSY_FORMATS = ["png", "gif"]


@pytest.mark.enable_socket
@pytest.mark.parametrize("image_type", LOSSY_FORMATS + UNLOSSY_FORMATS)
async def test_snapshot_url_with_abs_path(hass: HomeAssistant, local_server: BlockingHTTPServer, image_type: str) -> None:
    media_path: Path = Path(tempfile.mkdtemp())

    original_image_path = IMAGE_PATH / f"example_image.{image_type}"
    original_binary = io.FileIO(original_image_path, "rb").readall()
    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(original_binary, content_type=f"image/{image_type}")  # type: ignore
    retrieved_image_path = await snapshot_from_url(hass, snapshot_url, "notify-uuid-1", media_path, None)

    assert retrieved_image_path is not None
    retrieved_image = Image.open(retrieved_image_path)
    original_image = Image.open(original_image_path)
    assert retrieved_image.size == original_image.size
    if image_type in UNLOSSY_FORMATS:
        diff = ImageChops.difference(retrieved_image, original_image)
        assert diff.getbbox() is None


@pytest.mark.enable_socket
async def test_snapshot_url_with_jpeg_opts(hass: HomeAssistant, local_server: BlockingHTTPServer) -> None:
    media_path: Path = Path(tempfile.mkdtemp())

    original_image_path = IMAGE_PATH / "example_image.jpeg"
    original_binary = io.FileIO(original_image_path, "rb").readall()
    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(original_binary, content_type="image/jpeg")  # type: ignore
    retrieved_image_path: Path | None = await snapshot_from_url(
        hass,
        snapshot_url,
        "notify-uuid-1",
        media_path,
        None,
        jpeg_opts={"quality": 30, "progressive": True, "optimize": True, "comment": "changed by test"},
    )
    assert retrieved_image_path is not None

    retrieved_image: Image.Image = Image.open(str(retrieved_image_path))
    original_image: Image.Image = Image.open(str(original_image_path))
    assert retrieved_image.size == original_image.size
    assert retrieved_image.info.get("comment") == b"changed by test"
    assert retrieved_image.info.get("progressive") == 1


async def test_snapshot_url_with_broken_url(hass: HomeAssistant) -> None:
    media_path: Path = Path(tempfile.mkdtemp())
    snapshot_url = "http://no-such-domain.local:9494/snapshot_image_hass"
    retrieved_image_path = await snapshot_from_url(hass, snapshot_url, "notify-uuid-1", media_path, None)
    assert retrieved_image_path is None


async def test_snap_camera(mock_hass) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path: Path = Path(tmp_dir)
        image_path = await snap_camera(mock_hass, "camera.xunit", media_path=tmp_path, max_camera_wait=1)
    assert image_path is not None
    mock_hass.services.async_call.assert_awaited_once_with(
        "camera", "snapshot", service_data={"entity_id": "camera.xunit", "filename": image_path}
    )


@pytest.mark.parametrize("image_type", LOSSY_FORMATS + UNLOSSY_FORMATS)
async def test_snap_image(mock_context: Context, image_type: str) -> None:
    image_path = IMAGE_PATH / f"example_image.{image_type}"
    image_entity = MockImageEntity(image_path)
    if mock_context.hass:
        mock_context.hass.data["image"] = Mock(spec=EntityComponent)
        mock_context.hass.data["image"].get_entity = Mock(return_value=image_entity)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path: Path = Path(tmp_dir)
        snap_image_path = await snap_image(mock_context, "image.testing", media_path=tmp_path, notification_id="notify_001")
        assert snap_image_path is not None
        retrieved_image = Image.open(snap_image_path)

    original_image = Image.open(image_path)
    assert 'exif' not in retrieved_image.info
    assert retrieved_image.size == original_image.size
    if image_type in UNLOSSY_FORMATS:
        diff = ImageChops.difference(retrieved_image, original_image)
        assert diff.getbbox() is None


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
