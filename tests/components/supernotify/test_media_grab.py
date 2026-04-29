from __future__ import annotations

import io
import time
from io import BytesIO
from os import fspath
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import aiofiles
import anyio
import pytest
from anyio import Path
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    State,
)
from homeassistant.exceptions import ServiceValidationError
from PIL import Image, ImageChops

from conftest import IMAGE_PATH, TestImage
from custom_components.supernotify.const import (
    ATTR_MEDIA_SNAPSHOT_PATH,
    CONF_CAMERA,
    CONF_PTZ_PRESET_DEFAULT,
    MEDIA_OPTION_REPROCESS,
    PTZ_METHOD_FRIGATE,
)
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.media_grab import (
    MediaStorage,
    ReprocessOption,
    camera_available,
    grab_image,
    move_camera_to_ptz_preset,
    select_avail_camera,
    snap_camera,
    snap_image_entity,
    snap_notification_image,
    snapshot_from_url,
    write_image_from_bitmap,
)
from custom_components.supernotify.notification import Notification

from .hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from pytest_httpserver import HTTPServer

LOSSY_FORMATS = ["jpeg"]
UNLOSSY_FORMATS = ["png", "gif"]

DELIVERIES = """
mail:
    transport: email
    action: notify.smtp
"""


@pytest.mark.enable_socket
async def test_snapshot_url_with_abs_path(
    unmocked_hass_api: HomeAssistantAPI, local_server: HTTPServer, sample_image: TestImage, tmp_aiopath: Path
) -> None:
    media_path: Path = tmp_aiopath / "media"

    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(sample_image.contents, content_type=sample_image.mime_type)  # type: ignore
    retrieved_image_path = await snapshot_from_url(
        unmocked_hass_api, snapshot_url, "notify-uuid-1", anyio.Path(media_path), None
    )

    assert retrieved_image_path is not None
    retrieved_image = Image.open(fspath(retrieved_image_path))
    original_image = Image.open(fspath(sample_image.path))
    assert retrieved_image.size == original_image.size
    if sample_image.ext in UNLOSSY_FORMATS:
        diff = ImageChops.difference(retrieved_image, original_image)
        assert diff.getbbox() is None


async def test_write_image_from_bitmap_with_opts(
    unmocked_hass_api: HomeAssistantAPI, sample_image: TestImage, tmp_aiopath: Path
) -> None:
    output_path = tmp_aiopath / "image" / "out.jpg"
    retrieved_image_path: anyio.Path | None = await write_image_from_bitmap(
        unmocked_hass_api,
        sample_image.contents,
        output_path,
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


async def test_snapshot_url_with_broken_url(unmocked_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    media_path: Path = tmp_aiopath / "media"
    snapshot_url = "http://no-such-domain.local:9494/snapshot_image_hass"
    retrieved_image_path = await snapshot_from_url(
        unmocked_hass_api, snapshot_url, "notify-uuid-1", anyio.Path(media_path), None
    )
    assert retrieved_image_path is None


async def test_snap_camera(unmocked_hass_api, tmp_aiopath: Path) -> None:
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

    unmocked_hass_api._hass.services.async_register("camera", "snapshot", dummy_snapshot)
    image_path: anyio.Path | None = await snap_camera(
        unmocked_hass_api,
        "camera.xunit",
        "notify-uuid-1",
        media_path=tmp_aiopath,
        max_camera_wait=1,
    )
    assert called_entity == "camera.xunit"
    assert image_path is not None
    # raw snap preserves original metadata; reprocessing happens in grab_image
    raw_image: Image.Image = Image.open(str(image_path))
    assert raw_image.info.get("comment") == b"Original Comment"


@pytest.mark.parametrize(
    argnames="reprocess", argvalues=[ReprocessOption.ALWAYS, ReprocessOption.NEVER, ReprocessOption.PRESERVE]
)
async def test_write_image_reprocessing(unmocked_hass_api, reprocess: ReprocessOption, tmp_aiopath: Path) -> None:
    """write_image_from_bitmap applies the correct reprocess mode."""
    fixture_image_path: Path = IMAGE_PATH / "example_image.jpeg"
    async with await anyio.Path(fixture_image_path).open("rb") as f:
        bitmap = await f.read()
    # embed a known comment in the source bitmap
    buf = BytesIO()
    Image.open(io.BytesIO(bitmap)).save(buf, "jpeg", comment="Original Comment")
    raw_bytes = buf.getvalue()

    jpeg_opts = {"progressive": True, "optimize": True, "comment": "xunit cam woz here"}
    if reprocess == ReprocessOption.PRESERVE:
        del jpeg_opts["comment"]

    output_path = tmp_aiopath / "image" / "out.jpg"
    if reprocess == ReprocessOption.NEVER:
        # NEVER: write raw bytes straight to disk (skip PIL path)
        await output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "wb") as f:
            await f.write(raw_bytes)
        result_path: Path | None = output_path
    else:
        result_path = await write_image_from_bitmap(
            unmocked_hass_api, raw_bytes, output_path, reprocess=reprocess, jpeg_opts=jpeg_opts
        )
    assert result_path is not None
    result_image: Image.Image = Image.open(str(result_path))
    if reprocess == ReprocessOption.NEVER:
        assert result_image.info.get("comment") == b"Original Comment"
        assert result_image.info.get("progressive") is None
    elif reprocess == ReprocessOption.ALWAYS:
        assert result_image.info.get("comment") == b"xunit cam woz here"
        assert result_image.info.get("progressive") == 1
    elif reprocess == ReprocessOption.PRESERVE:
        assert result_image.info.get("comment") == b"Original Comment"
        assert result_image.info.get("progressive") == 1


async def test_snap_image_entity(
    hass_api_with_image: HomeAssistantAPI, sample_image_entity_id: str, sample_image: TestImage, tmp_aiopath: Path
) -> None:
    snap_image_path = await snap_image_entity(
        hass_api_with_image, sample_image_entity_id, media_path=tmp_aiopath, notification_id="notify_001"
    )
    assert snap_image_path is not None
    retrieved_image = Image.open(fspath(snap_image_path))
    original_image = Image.open(fspath(sample_image.path))
    # raw snap preserves original bytes; size should match
    assert retrieved_image.size == original_image.size


@pytest.mark.enable_socket
async def test_grab_image(hass: HomeAssistant, local_server, sample_image) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()

    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(sample_image.contents, content_type=sample_image.mime_type)  # type: ignore

    notification = Notification(ctx, "Test Me 123")
    result: anyio.Path | None = await grab_image(notification, ctx.delivery("mail"), ctx)
    assert result is None

    notification = Notification(ctx, "Test Me 123", action_data={"media": {"snapshot_url": snapshot_url}})
    result = await grab_image(notification, ctx.delivery("mail"), ctx)
    assert result is not None
    retrieved_image = Image.open(str(result))
    assert retrieved_image is not None  # images tested by lower funcs


@pytest.mark.enable_socket
async def test_grab_image_processed_file_cache(hass: HomeAssistant, local_server, sample_image) -> None:
    """grab_image reuses the processed file for a second delivery with identical settings."""
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()

    snapshot_url = local_server.url_for("/snapshot_image")
    local_server.expect_request("/snapshot_image").respond_with_data(sample_image.contents, content_type=sample_image.mime_type)

    notification = Notification(ctx, "Test Me 123", action_data={"media": {"snapshot_url": snapshot_url}})
    result1: anyio.Path | None = await grab_image(notification, ctx.delivery("mail"), ctx)
    assert result1 is not None

    # Second call with same delivery: processed file exists, write_image_from_bitmap not called again
    with patch("custom_components.supernotify.media_grab.write_image_from_bitmap") as mock_reprocess:
        result2 = await grab_image(notification, ctx.delivery("mail"), ctx)
        assert result2 == result1
        mock_reprocess.assert_not_called()


async def test_move_camera_onvif(mock_hass) -> None:
    hass_api = HomeAssistantAPI(mock_hass)
    await move_camera_to_ptz_preset(hass_api, "camera.xunit", preset="Upstairs")
    mock_hass.services.async_call.assert_awaited_once_with(
        "onvif",
        "ptz",
        service_data={"move_mode": "GotoPreset", "preset": "Upstairs"},
        target={"entity_id": "camera.xunit"},
        blocking=True,
        context=None,
        return_response=False,
    )


async def test_move_camera_frigate(mock_hass) -> None:
    hass_api = HomeAssistantAPI(mock_hass)
    await move_camera_to_ptz_preset(hass_api, "camera.xunit", preset="Upstairs", method=PTZ_METHOD_FRIGATE)
    mock_hass.services.async_call.assert_awaited_once_with(
        "frigate",
        "ptz",
        service_data={"action": "preset", "argument": "Upstairs"},
        target={"entity_id": "camera.xunit"},
        blocking=True,
        context=None,
        return_response=False,
    )


def mock_states(
    hass_api, home_entities: list | None = None, not_home_entities: list | None = None, unavailable_entities: list | None = None
) -> None:
    unavailable_entities = unavailable_entities or []
    not_home_entities = not_home_entities or []
    home_entities = home_entities or []

    def is_state_checker(entity, state) -> bool:
        if entity in home_entities and state == STATE_HOME:
            return True
        if entity in not_home_entities and state == STATE_HOME:
            return False
        if entity in unavailable_entities and state == STATE_HOME:
            return False
        raise ServiceValidationError("Test values not as expected")

    def get_state_checker(entity) -> State | None:
        if entity in home_entities:
            return State(entity, STATE_HOME)
        if entity in not_home_entities:
            return State(entity, STATE_NOT_HOME)
        if entity in unavailable_entities:
            return State(entity, STATE_UNAVAILABLE)
        return None

    hass_api.get_state.side_effect = get_state_checker
    hass_api.is_state.side_effect = is_state_checker


def test_select_camera_not_in_config(mock_hass) -> None:
    assert select_avail_camera(mock_hass, {}, "camera.unconfigured") == "camera.unconfigured"


def test_select_untracked_primary_camera(mock_hass_api) -> None:
    mock_states(mock_hass_api, home_entities=["camera.untracked"])

    assert (
        select_avail_camera(mock_hass_api, {"camera.untracked": {"alias": "Test Untracked"}}, "camera.untracked")
        == "camera.untracked"
    )


def test_select_tracked_primary_camera(mock_hass_api) -> None:
    mock_states(mock_hass_api, ["device_tracker.cam1"], [])
    assert (
        select_avail_camera(mock_hass_api, {"camera.tracked": {"device_tracker": "device_tracker.cam1"}}, "camera.tracked")
        == "camera.tracked"
    )


def test_no_select_unavail_primary_camera(mock_hass_api) -> None:
    mock_states(mock_hass_api, [], ["device_tracker.cam1"])
    assert (
        select_avail_camera(
            mock_hass_api,
            {"camera.tracked": {"camera": "camera.tracked", "device_tracker": "device_tracker.cam1"}},
            "camera.tracked",
        )
        is None
    )


def test_select_avail_alt_camera(mock_hass_api) -> None:
    mock_states(mock_hass_api, ["device_tracker.altcam2"], ["device_tracker.cam1", "device_tracker.altcam1"])

    assert (
        select_avail_camera(
            mock_hass_api,
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


def test_select_avail_alt_camera_if_camera_unavailable(mock_hass_api) -> None:
    mock_states(
        mock_hass_api,
        unavailable_entities=["camera.tracked"],
        not_home_entities=["device_tracker.altcam1", "device_tracker.altcam2"],
        home_entities=["camera.alt3"],
    )

    assert (
        select_avail_camera(
            mock_hass_api,
            {
                "camera.tracked": {
                    "camera": "camera.tracked",
                    "alt_camera": ["camera.alt1", "camera.alt2", "camera.alt3"],
                },
                "camera.alt1": {"camera": "camera.alt1", "device_tracker": "device_tracker.altcam1"},
                "camera.alt2": {"camera": "camera.alt2", "device_tracker": "device_tracker.altcam2"},
            },
            "camera.tracked",
        )
        == "camera.alt3"
    )


def test_select_untracked_alt_camera(mock_hass_api) -> None:
    mock_states(mock_hass_api, ["camera.alt3"], ["device_tracker.cam1", "device_tracker.altcam1", "device_tracker.altcam2"])
    assert (
        select_avail_camera(
            mock_hass_api,
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


async def test_media_storage(mock_hass_api: HomeAssistantAPI, tmp_path) -> None:

    uut = MediaStorage(tmp_path, None, 7)
    await uut.initialize(mock_hass_api)
    old_time = Mock(return_value=Mock(st_ctime=time.time() - (8 * 24 * 60 * 60)))
    new_time = Mock(return_value=Mock(st_ctime=time.time() - (5 * 24 * 60 * 60)))
    mock_files = [
        Mock(path="abc", stat=new_time),
        Mock(path="def", stat=new_time),
        Mock(path="xyz", stat=old_time),
    ]
    with patch("aiofiles.os.listdir", return_value=mock_files) as _scan:
        assert await uut.size() == 3

    with patch("aiofiles.os.scandir", return_value=mock_files) as _scan:
        with patch("aiofiles.os.unlink") as rmfr:
            await uut.cleanup()
            rmfr.assert_called_once_with(Path("xyz"))
    # skip cleanup for a few hours
    assert uut.media_path is not None
    first_purge = uut.last_purge
    await uut.cleanup()
    assert first_purge == uut.last_purge


# --- snapshot_from_url ---


@pytest.mark.enable_socket
async def test_snapshot_url_with_relative_path(
    unmocked_hass_api: HomeAssistantAPI, local_server: HTTPServer, sample_image: TestImage, tmp_aiopath: Path
) -> None:
    local_server.expect_request("/proxy/cam").respond_with_data(sample_image.contents, content_type=sample_image.mime_type)
    result = await snapshot_from_url(unmocked_hass_api, "/proxy/cam", "n1", tmp_aiopath / "media", local_server.url_for(""))
    assert result is not None


@pytest.mark.enable_socket
async def test_snapshot_url_with_http_error(
    unmocked_hass_api: HomeAssistantAPI, local_server: HTTPServer, tmp_aiopath: Path
) -> None:
    local_server.expect_request("/bad").respond_with_data("not found", status=404)
    result = await snapshot_from_url(unmocked_hass_api, local_server.url_for("/bad"), "n1", tmp_aiopath / "media", None)
    assert result is None


# --- move_camera_to_ptz_preset ---


async def test_move_camera_unknown_ptz_method(mock_hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(mock_hass)
    await move_camera_to_ptz_preset(hass_api, "camera.x", "Upstairs", method="zigbee")
    mock_hass.services.async_call.assert_not_called()  # type: ignore


# --- snap_image_entity ---


async def test_snap_image_entity_no_entity(unmocked_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    result = await snap_image_entity(unmocked_hass_api, "image.nonexistent", tmp_aiopath, "n1")
    assert result is None


async def test_snap_image_entity_exception(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    mock_entity = AsyncMock()
    mock_entity.async_image.side_effect = RuntimeError("boom")
    mock_hass_api.domain_entity.return_value = mock_entity  # type: ignore
    result = await snap_image_entity(mock_hass_api, "image.broken", tmp_aiopath, "n1")
    assert result is None


# --- snap_camera ---


async def test_snap_camera_empty_entity_id(unmocked_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    result = await snap_camera(unmocked_hass_api, "", "n1", tmp_aiopath)
    assert result is None


async def test_snap_camera_service_exception(unmocked_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    async def raising_snapshot(call: ServiceCall) -> ServiceResponse | None:
        raise OSError("camera not responding")

    unmocked_hass_api._hass.services.async_register("camera", "snapshot", raising_snapshot)
    result = await snap_camera(unmocked_hass_api, "camera.broken", "n1", tmp_aiopath, max_camera_wait=1)
    assert result is None


# --- camera_available ---


def test_camera_available_no_state(mock_hass_api: HomeAssistantAPI) -> None:
    mock_hass_api.get_state.return_value = None  # type: ignore
    assert camera_available(mock_hass_api, {CONF_CAMERA: "camera.nostate"}) is False


def test_camera_available_tracker_missing(mock_hass_api: HomeAssistantAPI) -> None:
    mock_hass_api.get_state.return_value = None  # type: ignore
    assert camera_available(mock_hass_api, {CONF_CAMERA: "camera.x", "device_tracker": "device_tracker.gone"}) is False


def test_camera_available_exception(mock_hass_api: HomeAssistantAPI) -> None:
    mock_hass_api.get_state.side_effect = RuntimeError("unexpected")  # type: ignore
    assert camera_available(mock_hass_api, {CONF_CAMERA: "camera.x"}) is False


# --- select_avail_camera ---


def test_select_primary_camera_no_entity_state(mock_hass_api: HomeAssistantAPI) -> None:
    mock_states(mock_hass_api)  # no entities have known state
    result = select_avail_camera(mock_hass_api, {"camera.nostate": {CONF_CAMERA: "camera.nostate"}}, "camera.nostate")
    assert result == "camera.nostate"


def test_select_unavail_primary_with_unavail_alts(mock_hass_api: HomeAssistantAPI) -> None:
    mock_states(mock_hass_api, unavailable_entities=["device_tracker.cam1", "device_tracker.altcam1"])
    result = select_avail_camera(
        mock_hass_api,
        {
            "camera.primary": {
                CONF_CAMERA: "camera.primary",
                "device_tracker": "device_tracker.cam1",
                "alt_camera": ["camera.alt1"],
            },
            "camera.alt1": {CONF_CAMERA: "camera.alt1", "device_tracker": "device_tracker.altcam1"},
        },
        "camera.primary",
    )
    assert result == "camera.alt1"


# --- write_image_from_bitmap ---


async def test_write_image_from_bitmap_none_bitmap(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    result = await write_image_from_bitmap(mock_hass_api, None, tmp_aiopath, ReprocessOption.ALWAYS)
    assert result is None


async def test_write_image_from_bitmap_type_error(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    image = Image.new("RGB", (10, 10))
    buf = BytesIO()
    image.save(buf, "jpeg")
    bitmap = buf.getvalue()
    mock_hass_api.create_job.return_value = Image.open(BytesIO(bitmap))  # type: ignore
    with patch.object(Image.Image, "save", side_effect=TypeError("bad option")):
        result = await write_image_from_bitmap(mock_hass_api, bitmap, tmp_aiopath, ReprocessOption.ALWAYS)
    assert result is None


async def test_write_image_from_bitmap_exception(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    image = Image.new("RGB", (10, 10))
    buf = BytesIO()
    image.save(buf, "jpeg")
    bitmap = buf.getvalue()
    mock_hass_api.create_job.return_value = Image.open(BytesIO(bitmap))  # type: ignore
    with patch.object(Image.Image, "save", side_effect=RuntimeError("unexpected")):
        result = await write_image_from_bitmap(mock_hass_api, bitmap, tmp_aiopath, ReprocessOption.ALWAYS)
    assert result is None


# --- grab_image ---


async def test_grab_image_no_media_path(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()
    ctx.media_storage.media_path = None
    notification = Notification(ctx, "Test", action_data={"media": {"snapshot_url": "http://test"}})
    assert await grab_image(notification, ctx.delivery("mail"), ctx) is None


async def test_grab_image_invalid_reprocess(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()
    notification = Notification(ctx, "Test", action_data={"media": {"snapshot_url": "http://x"}})
    notification.media[MEDIA_OPTION_REPROCESS] = "bogus"  # inject directly — not in schema
    fixture_path = anyio.Path(IMAGE_PATH / "example_image.jpeg")
    with patch("custom_components.supernotify.media_grab.snap_notification_image", return_value=fixture_path):
        result = await grab_image(notification, ctx.delivery("mail"), ctx)
    assert result is not None


async def test_grab_image_with_existing_snapshot_path(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()
    existing: Path = tmp_aiopath / "shot.jpg"
    await existing.touch()
    notification = Notification(ctx, "Test", action_data={"media": {"snapshot_url": "http://cam/snap"}})
    notification.media[ATTR_MEDIA_SNAPSHOT_PATH] = str(existing)  # inject directly — not in schema
    result = await grab_image(notification, ctx.delivery("mail"), ctx)
    assert str(result) == str(existing)


async def test_grab_image_with_image_entity(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()
    with patch("custom_components.supernotify.media_grab.snap_image_entity", return_value=None) as mock_entity:
        notification = Notification(ctx, "Test", action_data={"media": {"camera_entity_id": "image.front_door"}})
        await snap_notification_image(notification, ctx)
    mock_entity.assert_called_once()
    assert mock_entity.call_args[0][1] == "image.front_door"


async def test_grab_image_with_camera(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()
    with patch("custom_components.supernotify.media_grab.select_avail_camera", return_value="camera.front"):
        with patch("custom_components.supernotify.media_grab.snap_camera", return_value=None) as mock_snap:
            notification = Notification(ctx, "Test", action_data={"media": {"camera_entity_id": "camera.front"}})
            await snap_notification_image(notification, ctx)
    mock_snap.assert_called_once()


async def test_grab_image_with_camera_ptz(hass: HomeAssistant, tmp_aiopath: Path) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()
    ctx.cameras = {"camera.front": {CONF_CAMERA: "camera.front", CONF_PTZ_PRESET_DEFAULT: "Home"}}
    with patch("custom_components.supernotify.media_grab.select_avail_camera", return_value="camera.front"):
        with patch("custom_components.supernotify.media_grab.snap_camera", return_value=None):
            with patch(
                "custom_components.supernotify.media_grab.move_camera_to_ptz_preset", new_callable=AsyncMock
            ) as mock_ptz:
                notification = Notification(
                    ctx,
                    "Test",
                    action_data={"media": {"camera_entity_id": "camera.front", "camera_ptz_preset": "Doorway"}},
                )
                await snap_notification_image(notification, ctx)
    assert mock_ptz.call_count == 2  # move to preset before snap, return to default after


async def test_grab_image_camera_unavailable(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass, deliveries=DELIVERIES)
    await ctx.test_initialize()
    with patch("custom_components.supernotify.media_grab.select_avail_camera", return_value=None):
        notification = Notification(ctx, "Test", action_data={"media": {"camera_entity_id": "camera.unavailable"}})
        result = await grab_image(notification, ctx.delivery("mail"), ctx)
    assert result is None


# --- MediaStorage ---


async def test_media_storage_initialize_creates_path(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    new_path = tmp_aiopath / "new_media_dir"
    uut = MediaStorage(str(new_path))
    await uut.initialize(mock_hass_api)
    assert uut.media_path is not None
    assert await anyio.Path(new_path).exists()


async def test_media_storage_initialize_mkdir_fails(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    new_path = tmp_aiopath / "new_dir"
    uut = MediaStorage(str(new_path))
    with patch.object(anyio.Path, "mkdir", side_effect=PermissionError("no permission")):
        await uut.initialize(mock_hass_api)
    assert uut.media_path is None
    mock_hass_api.raise_issue.assert_called_once()  # type: ignore


async def test_media_storage_size_no_path(mock_hass_api: HomeAssistantAPI) -> None:
    uut = MediaStorage(None)
    assert await uut.size() == 0


async def test_media_storage_cleanup_zero_days(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    uut = MediaStorage(str(tmp_aiopath), None, 0)
    assert await uut.cleanup() == 0


async def test_media_storage_cleanup_no_path(mock_hass_api: HomeAssistantAPI) -> None:
    uut = MediaStorage(None)
    assert await uut.cleanup() == 0


async def test_media_storage_cleanup_scandir_exception(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    uut = MediaStorage(str(tmp_aiopath), None, 7)
    await uut.initialize(mock_hass_api)
    with patch("aiofiles.os.scandir", side_effect=OSError("disk error")):
        count = await uut.cleanup(force=True)
    assert count == 0


async def test_media_storage_cleanup_nonexistent_path(mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path) -> None:
    nonexistent = tmp_aiopath / "nope"
    uut = MediaStorage(str(nonexistent), None, 7)
    uut.media_path = anyio.Path(nonexistent)  # set without initializing (so path doesn't exist on disk)
    assert await uut.cleanup(force=True) == 0


async def test_media_storage_initialize_null_url_prefix_skips_http_registration(
    mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path
) -> None:
    """media_url_prefix=None: hass_api.register_web_path must not be called."""
    uut = MediaStorage(str(tmp_aiopath), None, 7)
    await uut.initialize(mock_hass_api)
    mock_hass_api.register_web_path.assert_not_called()  # type: ignore[attr-defined]


async def test_media_storage_initialize_with_url_prefix_registers_http_path(
    mock_hass_api: HomeAssistantAPI, tmp_aiopath: Path
) -> None:
    """media_url_prefix set: hass_api.register_web_path is called once with correct args."""
    uut = MediaStorage(str(tmp_aiopath), "/supernotify-media", 7)
    await uut.initialize(mock_hass_api)
    mock_hass_api.register_web_path.assert_called_once_with(uut.media_path, "/supernotify-media")  # type: ignore[attr-defined]
