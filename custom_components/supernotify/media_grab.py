import asyncio
import io
import logging
import time
from enum import StrEnum, auto
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import anyio
from aiohttp import ClientTimeout
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from PIL import Image

from custom_components.supernotify import (
    ATTR_JPEG_OPTS,
    ATTR_MEDIA_CAMERA_DELAY,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CAMERA_PTZ_PRESET,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_PNG_OPTS,
    CONF_ALT_CAMERA,
    CONF_CAMERA,
    CONF_DEVICE_TRACKER,
    CONF_OPTIONS,
    CONF_PTZ_DELAY,
    CONF_PTZ_METHOD,
    CONF_PTZ_PRESET_DEFAULT,
    MEDIA_OPTION_REPROCESS,
    OPTION_JPEG,
    OPTION_PNG,
    PTZ_METHOD_FRIGATE,
    PTZ_METHOD_ONVIF,
)

from .context import Context

if TYPE_CHECKING:
    from homeassistant.components.image import ImageEntity

_LOGGER = logging.getLogger(__name__)


class ReprocessOption(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    PRESERVE = auto()


async def snapshot_from_url(
    hass: HomeAssistant | None,
    snapshot_url: str,
    notification_id: str,
    media_path: Path,
    hass_base_url: str | None,
    remote_timeout: int = 15,
    reprocess: ReprocessOption = ReprocessOption.ALWAYS,
    jpeg_opts: dict[str, Any] | None = None,
    png_opts: dict[str, Any] | None = None,
) -> Path | None:
    hass_base_url = hass_base_url or ""
    if not hass:
        raise ValueError("HomeAssistant not available")
    try:
        media_dir: anyio.Path = anyio.Path(media_path) / "snapshot"
        await media_dir.mkdir(parents=True, exist_ok=True)

        if snapshot_url.startswith("http"):
            image_url = snapshot_url
        else:
            image_url = f"{hass_base_url}{snapshot_url}"
        websession = async_get_clientsession(hass)
        r = await websession.get(image_url, timeout=ClientTimeout(total=remote_timeout))
        if r.status != HTTPStatus.OK:
            _LOGGER.warning("SUPERNOTIFY Unable to retrieve %s: %s", image_url, r.status)
        else:
            bitmap: bytes | None = await r.content.read()
            image_path: anyio.Path | None = await write_image_from_bitmap(
                bitmap, media_path, notification_id, reprocess=reprocess, jpeg_opts=jpeg_opts, png_opts=png_opts
            )
            if image_path:
                _LOGGER.debug("SUPERNOTIFY Fetched image from %s to %s", image_url, image_path)
                return Path(image_path)

        _LOGGER.warning("SUPERNOTIFY Failed to snap image from %s", snapshot_url)
    except Exception as e:
        _LOGGER.error("SUPERNOTIFY Image snap fail: %s", e)

    return None


async def move_camera_to_ptz_preset(
    hass: HomeAssistant, camera_entity_id: str, preset: str | int, method: str = PTZ_METHOD_ONVIF
) -> None:
    try:
        _LOGGER.info("SUPERNOTIFY Executing PTZ by %s to %s for %s", method, preset, camera_entity_id)
        if method == PTZ_METHOD_FRIGATE:
            await hass.services.async_call(
                "frigate",
                "ptz",
                service_data={"action": "preset", "argument": preset},
                target={
                    "entity_id": camera_entity_id,
                },
            )
        elif method == PTZ_METHOD_ONVIF:
            await hass.services.async_call(
                "onvif",
                "ptz",
                service_data={"move_mode": "GotoPreset", "preset": preset},
                target={
                    "entity_id": camera_entity_id,
                },
            )
        else:
            _LOGGER.warning("SUPERNOTIFY Unknown PTZ method %s", method)
    except Exception as e:
        _LOGGER.warning("SUPERNOTIFY Unable to move %s to ptz preset %s: %s", camera_entity_id, preset, e)


async def snap_image_entity(
    context: Context,
    entity_id: str,
    media_path: Path,
    notification_id: str,
    reprocess: ReprocessOption = ReprocessOption.ALWAYS,
    jpeg_opts: dict[str, Any] | None = None,
    png_opts: dict[str, Any] | None = None,
) -> Path | None:
    """Use for any image, including MQTT Image"""
    image_path: anyio.Path | None = None
    try:
        image_entity: ImageEntity | None = None
        if context.hass_api._hass:
            # TODO: must be a better hass method than this
            image_entity = context.hass_api._hass.data["image"].get_entity(entity_id)
        if image_entity:
            bitmap: bytes | None = await image_entity.async_image()
            image_path = await write_image_from_bitmap(
                bitmap, media_path, notification_id, reprocess=reprocess, jpeg_opts=jpeg_opts, png_opts=png_opts
            )
    except Exception as e:
        _LOGGER.warning("SUPERNOTIFY Unable to snap image %s: %s", entity_id, e)
    if image_path is None:
        _LOGGER.warning("SUPERNOTIFY Unable to save from image entity %s", entity_id)
    return Path(image_path) if image_path else None


async def snap_camera(
    hass: HomeAssistant,
    camera_entity_id: str,
    notification_id: str,
    media_path: Path,
    max_camera_wait: int = 20,
    reprocess: ReprocessOption = ReprocessOption.ALWAYS,
    jpeg_opts: dict[str, Any] | None = None,
    png_opts: dict[str, Any] | None = None,
) -> Path | None:
    image_path: Path | None = None
    if not camera_entity_id:
        _LOGGER.warning("SUPERNOTIFY Empty camera entity id for snap")
        return image_path

    try:
        media_dir: anyio.Path = anyio.Path(media_path) / "camera"
        await media_dir.mkdir(parents=True, exist_ok=True)
        timed = str(time.time()).replace(".", "_")
        image_path = Path(media_dir) / f"{camera_entity_id}_{timed}.jpg"
        await hass.services.async_call(
            "camera", "snapshot", service_data={"entity_id": camera_entity_id, "filename": image_path}
        )

        # give async service time
        cutoff_time = time.time() + max_camera_wait
        while time.time() < cutoff_time and not image_path.exists():
            _LOGGER.info("Image file not available yet at %s, pausing", image_path)
            await asyncio.sleep(1)

        if reprocess != ReprocessOption.NEVER:
            async with await anyio.Path(image_path).open("rb") as f:
                bitmap: bytes | None = await f.read()
                async_path: anyio.Path | None = await write_image_from_bitmap(
                    bitmap, media_path, notification_id, reprocess=reprocess, jpeg_opts=jpeg_opts, png_opts=png_opts
                )
                if async_path:
                    image_path = Path(async_path)
                else:
                    _LOGGER.warning("SUPERNOTIFY Unable to reprocess camera image")

    except Exception as e:
        _LOGGER.warning("Failed to snap avail camera %s to %s: %s", camera_entity_id, image_path, e)
        image_path = None

    return image_path


def select_avail_camera(hass: HomeAssistant, cameras: dict[str, Any], camera_entity_id: str) -> str | None:
    avail_camera_entity_id: str | None = None

    try:
        preferred_cam = cameras.get(camera_entity_id)

        if not preferred_cam or not preferred_cam.get(CONF_DEVICE_TRACKER):
            # assume unconfigured camera, or configured without tracker, available
            avail_camera_entity_id = camera_entity_id
        elif hass.states.is_state(preferred_cam[CONF_DEVICE_TRACKER], STATE_HOME):
            avail_camera_entity_id = camera_entity_id
        else:
            alt_cams_with_tracker = [
                cameras[c]
                for c in preferred_cam.get(CONF_ALT_CAMERA, [])
                if c in cameras and cameras[c].get(CONF_DEVICE_TRACKER)
            ]
            for alt_cam in alt_cams_with_tracker:
                tracker_entity_id = alt_cam.get(CONF_DEVICE_TRACKER)
                if tracker_entity_id and hass.states.is_state(tracker_entity_id, STATE_HOME):
                    avail_camera_entity_id = alt_cam[CONF_CAMERA]
                    _LOGGER.info(
                        "SUPERNOTIFY Selecting available camera %s rather than %s", avail_camera_entity_id, camera_entity_id
                    )
                    break
            if avail_camera_entity_id is None:
                alt_cam_ids_without_tracker = [
                    c
                    for c in preferred_cam.get(CONF_ALT_CAMERA, [])
                    if c not in cameras or not cameras[c].get(CONF_DEVICE_TRACKER)
                ]
                if len(alt_cam_ids_without_tracker) > 0:
                    _LOGGER.info(
                        "SUPERNOTIFY Selecting untracked camera %s rather than %s", avail_camera_entity_id, camera_entity_id
                    )
                    avail_camera_entity_id = alt_cam_ids_without_tracker[0]

        if avail_camera_entity_id is None:
            _LOGGER.warning("%s not available and no alternative available", camera_entity_id)
            for c in cameras.values():
                if c.get(CONF_DEVICE_TRACKER):
                    _LOGGER.debug(
                        "SUPERNOTIFY Tracker %s: %s", c.get(CONF_DEVICE_TRACKER), hass.states.get(c[CONF_DEVICE_TRACKER])
                    )

    except Exception as e:
        _LOGGER.warning("SUPERNOTIFY Unable to select available camera: %s", e)

    return avail_camera_entity_id


async def grab_image(notification: "Notification", delivery_name: str, context: Context) -> Path | None:  # type: ignore  # noqa: F821
    snapshot_url = notification.media.get(ATTR_MEDIA_SNAPSHOT_URL)
    camera_entity_id = notification.media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
    delivery_config = notification.delivery_data(delivery_name)
    jpeg_opts = notification.media.get(ATTR_JPEG_OPTS, delivery_config.get(CONF_OPTIONS, {}).get(OPTION_JPEG))
    png_opts = notification.media.get(ATTR_PNG_OPTS, delivery_config.get(CONF_OPTIONS, {}).get(OPTION_PNG))
    reprocess_option = (
        notification.media.get(MEDIA_OPTION_REPROCESS, delivery_config.get(CONF_OPTIONS, {}).get(MEDIA_OPTION_REPROCESS))
        or "always"
    )

    reprocess: ReprocessOption = ReprocessOption.ALWAYS
    try:
        reprocess = ReprocessOption(reprocess_option)
    except Exception:
        _LOGGER.warning("SUPERNOTIFY Invalid reprocess option: %s", reprocess_option)

    if not snapshot_url and not camera_entity_id:
        return None

    image_path: Path | None = None
    if notification.snapshot_image_path is not None:
        return notification.snapshot_image_path  # type: ignore
    if snapshot_url and context.media_path and context.hass_api:
        image_path = await snapshot_from_url(
            context.hass_api._hass,
            snapshot_url,
            notification.id,
            context.media_path,
            context.hass_api.internal_url,
            reprocess=reprocess,
            jpeg_opts=jpeg_opts,
            png_opts=png_opts,
        )
    elif camera_entity_id and camera_entity_id.startswith("image.") and context.hass_api._hass and context.media_path:
        image_path = await snap_image_entity(
            context,
            camera_entity_id,
            context.media_path,
            notification.id,
            reprocess=reprocess,
            jpeg_opts=jpeg_opts,
            png_opts=png_opts,
        )
    elif camera_entity_id:
        if not context.hass_api._hass or not context.media_path:
            _LOGGER.warning("SUPERNOTIFY No HA ref or media path for camera %s", camera_entity_id)
            return None
        active_camera_entity_id = select_avail_camera(context.hass_api._hass, context.cameras, camera_entity_id)
        if active_camera_entity_id:
            camera_config = context.cameras.get(active_camera_entity_id, {})
            camera_delay = notification.media.get(ATTR_MEDIA_CAMERA_DELAY, camera_config.get(CONF_PTZ_DELAY))
            camera_ptz_preset_default = camera_config.get(CONF_PTZ_PRESET_DEFAULT)
            camera_ptz_method = camera_config.get(CONF_PTZ_METHOD)
            camera_ptz_preset = notification.media.get(ATTR_MEDIA_CAMERA_PTZ_PRESET)
            _LOGGER.debug(
                "SUPERNOTIFY snapping camera %s, ptz %s->%s, delay %s secs",
                active_camera_entity_id,
                camera_ptz_preset,
                camera_ptz_preset_default,
                camera_delay,
            )
            if camera_ptz_preset:
                await move_camera_to_ptz_preset(
                    context.hass_api._hass, active_camera_entity_id, camera_ptz_preset, method=camera_ptz_method
                )
            if camera_delay:
                _LOGGER.debug("SUPERNOTIFY Waiting %s secs before snapping", camera_delay)
                await asyncio.sleep(camera_delay)
            image_path = await snap_camera(
                context.hass_api._hass,
                active_camera_entity_id,
                notification.id,
                reprocess=reprocess,
                media_path=context.media_path,
                max_camera_wait=15,
                jpeg_opts=jpeg_opts,
                png_opts=png_opts,
            )
            if camera_ptz_preset and camera_ptz_preset_default:
                await move_camera_to_ptz_preset(
                    context.hass_api._hass, active_camera_entity_id, camera_ptz_preset_default, method=camera_ptz_method
                )

    if image_path is None:
        _LOGGER.warning("SUPERNOTIFY No media available to attach (%s,%s)", snapshot_url, camera_entity_id)
        return None
    # TODO: replace poking inside notification
    notification.snapshot_image_path = image_path
    return image_path


async def write_image_from_bitmap(
    bitmap: bytes | None,
    media_path: Path,
    notification_id: str,
    reprocess: ReprocessOption = ReprocessOption.ALWAYS,
    output_format: str | None = None,
    jpeg_opts: dict[str, Any] | None = None,
    png_opts: dict[str, Any] | None = None,
) -> anyio.Path | None:
    image_path: anyio.Path | None = None
    if bitmap is None:
        _LOGGER.debug("SUPERNOTIFY Empty bitmap for image")
        return None
    try:
        media_dir: anyio.Path = anyio.Path(media_path) / "image"
        if not await media_dir.exists():
            await media_dir.mkdir(parents=True, exist_ok=True)

        image: Image.Image = Image.open(io.BytesIO(bitmap))
        input_format = image.format.lower() if image.format else "img"
        if reprocess == ReprocessOption.ALWAYS:
            # rewrite to remove metadata, incl custom CCTV comments that confusie python MIMEImage
            clean_image: Image.Image = Image.new(image.mode, image.size)
            clean_image.putdata(image.getdata())
            image = clean_image

        buffer = BytesIO()
        img_args = {}
        if reprocess in (ReprocessOption.ALWAYS, ReprocessOption.PRESERVE):
            if input_format in ("jpg", "jpeg") and jpeg_opts:
                img_args.update(jpeg_opts)
            elif input_format == "png" and png_opts:
                img_args.update(png_opts)

        output_format = output_format or input_format
        image.save(buffer, output_format, **img_args)

        media_ext: str = output_format if output_format else "img"
        timed: str = str(time.time()).replace(".", "_")
        image_path = anyio.Path(media_dir) / f"{notification_id}_{timed}.{media_ext}"
        image_path = await image_path.resolve()
        async with aiofiles.open(image_path, "wb") as file:
            await file.write(buffer.getbuffer())
    except TypeError:
        # probably a jpeg or png option
        _LOGGER.exception("SUPERNOTIFY Image snap fail")
    except Exception:
        _LOGGER.exception("SUPERNOTIFY Failure saving %s bitmap", input_format)
        image_path = None
    return image_path
