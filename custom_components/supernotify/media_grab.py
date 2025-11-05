import asyncio
import io
import logging
import time
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
    CONF_ALT_CAMERA,
    CONF_CAMERA,
    CONF_DEVICE_TRACKER,
    PTZ_METHOD_FRIGATE,
    PTZ_METHOD_ONVIF,
)
from custom_components.supernotify.context import Context

if TYPE_CHECKING:
    from homeassistant.components.image import ImageEntity

_LOGGER = logging.getLogger(__name__)


async def snapshot_from_url(
    hass: HomeAssistant,
    snapshot_url: str,
    notification_id: str,
    media_path: Path,
    hass_base_url: str | None,
    remote_timeout: int = 15,
    jpeg_opts: dict[str, Any] | None = None,
) -> Path | None:
    hass_base_url = hass_base_url or ""
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
            if r.content_type in ("image/jpeg", "image/jpg"):
                media_ext = "jpg"
                image_format = "JPEG"
            elif r.content_type == "image/png":
                media_ext = "png"
                image_format = "PNG"
            elif r.content_type == "image/gif":
                media_ext = "gif"
                image_format = "GIF"
            else:
                _LOGGER.info("SUPERNOTIFY Unexpected MIME type %s from snap of %s", r.content_type, image_url)
                media_ext = "img"
                image_format = None

            # TODO: configure image rewrite
            image_path: Path = Path(media_dir) / f"{notification_id}.{media_ext}"
            image: Image.Image = Image.open(io.BytesIO(await r.content.read()))
            # rewrite to remove metadata, incl custom CCTV comments that confusie python MIMEImage
            clean_image: Image.Image = Image.new(image.mode, image.size)
            clean_image.putdata(image.getdata())
            buffer = BytesIO()
            img_args = {}
            if image_format == "JPEG" and jpeg_opts:
                img_args.update(jpeg_opts)
            clean_image.save(buffer, image_format, **img_args)
            async with aiofiles.open(image_path, "wb") as file:
                await file.write(buffer.getbuffer())
            _LOGGER.debug("SUPERNOTIFY Fetched image from %s to %s", image_url, image_path)
            return image_path
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


async def snap_image(
    context: Context,
    entity_id: str,
    media_path: Path,
    notification_id: str,
    jpeg_opts: dict[str, Any] | None = None,
) -> Path | None:
    """Use for any image, including MQTT Image"""
    image_path: anyio.Path | None = None
    try:
        image_entity: ImageEntity | None = None
        if context.hass:
            image_entity = context.hass.data["image"].get_entity(entity_id)
        if image_entity:
            bitmap: bytes | None = await image_entity.async_image()
            if bitmap is None:
                _LOGGER.warning("SUPERNOTIFY Empty bitmap from image entity %s", entity_id)
            else:
                image: Image.Image = Image.open(io.BytesIO(bitmap))
                media_dir: anyio.Path = anyio.Path(media_path) / "image"
                await media_dir.mkdir(parents=True, exist_ok=True)

                media_ext: str = image.format.lower() if image.format else "img"
                timed: str = str(time.time()).replace(".", "_")
                image_path = anyio.Path(media_dir) / f"{notification_id}_{timed}.{media_ext}"
                buffer = BytesIO()
                img_args = {}
                if media_ext in ("jpg", "jpeg") and jpeg_opts:
                    img_args.update(jpeg_opts)
                image.save(buffer, image.format, **img_args)
                async with aiofiles.open(await image_path.resolve(), "wb") as file:
                    await file.write(buffer.getbuffer())
        else:
            _LOGGER.warning("SUPERNOTIFY Unable to find image entity %s", entity_id)
    except Exception as e:
        _LOGGER.warning("SUPERNOTIFY Unable to snap image %s: %s", entity_id, e)
        return None
    return Path(await image_path.resolve()) if image_path else None


async def snap_camera(
    hass: HomeAssistant,
    camera_entity_id: str,
    media_path: Path,
    max_camera_wait: int = 20,
    jpeg_opts: dict[str, Any] | None = None,
) -> Path | None:
    image_path: Path | None = None
    if not camera_entity_id:
        _LOGGER.warning("SUPERNOTIFY Empty camera entity id for snap")
        return image_path
    if jpeg_opts:
        _LOGGER.warning("jpeg_opts not yet supported by snap_camera")

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
