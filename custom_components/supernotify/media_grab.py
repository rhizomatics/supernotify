from __future__ import annotations

import asyncio
import datetime as dt
import io
import logging
import time
from enum import StrEnum, auto
from http import HTTPStatus
from io import BytesIO
from typing import TYPE_CHECKING, Any, cast

import aiofiles
import aiofiles.os
import homeassistant.util.dt as dt_util
from aiohttp import ClientResponse, ClientSession, ClientTimeout
from anyio import Path
from homeassistant.const import STATE_HOME, STATE_UNAVAILABLE
from PIL import Image

from custom_components.supernotify.const import (
    ATTR_JPEG_OPTS,
    ATTR_MEDIA_CAMERA_DELAY,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CAMERA_PTZ_PRESET,
    ATTR_MEDIA_SNAPSHOT_PATH,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_PNG_OPTS,
    CONF_ALT_CAMERA,
    CONF_CAMERA,
    CONF_DEVICE_TRACKER,
    CONF_OPTIONS,
    CONF_PTZ_CAMERA,
    CONF_PTZ_DELAY,
    CONF_PTZ_METHOD,
    CONF_PTZ_PRESET_DEFAULT,
    MEDIA_OPTION_REPROCESS,
    OPTION_JPEG,
    OPTION_PNG,
    PTZ_METHOD_FRIGATE,
    PTZ_METHOD_ONVIF,
)

if TYPE_CHECKING:
    from homeassistant.components.image import ImageEntity
    from homeassistant.core import State

    from .context import Context
    from .hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


class ReprocessOption(StrEnum):
    ALWAYS = auto()
    NEVER = auto()
    PRESERVE = auto()


async def snapshot_from_url(
    hass_api: HomeAssistantAPI,
    snapshot_url: str,
    notification_id: str,
    media_path: Path,
    hass_base_url: str | None,
    remote_timeout: int = 15,
) -> Path | None:
    """Download a snapshot URL and save raw bytes. No reprocessing."""
    hass_base_url = hass_base_url or ""
    try:
        raw_dir: Path = Path(media_path) / "raw"
        await raw_dir.mkdir(parents=True, exist_ok=True)

        image_url = snapshot_url if snapshot_url.startswith("http") else f"{hass_base_url}{snapshot_url}"
        websession: ClientSession = hass_api.http_session()
        r: ClientResponse = await websession.get(image_url, timeout=ClientTimeout(total=remote_timeout))
        if r.status != HTTPStatus.OK:
            _LOGGER.warning("SUPERNOTIFY Unable to retrieve %s: %s", image_url, r.status)
        else:
            bitmap: bytes | None = await r.content.read()
            if bitmap:
                ext = _detect_image_ext(bitmap)
                raw_path: Path = raw_dir / f"{notification_id}.{ext}"
                async with aiofiles.open(raw_path, "wb") as f:
                    await f.write(bitmap)
                _LOGGER.debug("SUPERNOTIFY Fetched raw image from %s to %s", image_url, raw_path)
                return raw_path

        _LOGGER.warning("SUPERNOTIFY Failed to snap image from %s", snapshot_url)
    except Exception as e:
        _LOGGER.exception("SUPERNOTIFY Image snap fail: %s", e)

    return None


async def move_camera_to_ptz_preset(
    hass_api: HomeAssistantAPI, camera_entity_id: str, preset: str | int, method: str = PTZ_METHOD_ONVIF
) -> None:
    try:
        _LOGGER.info("SUPERNOTIFY Executing PTZ by %s to %s for %s", method, preset, camera_entity_id)
        if method == PTZ_METHOD_FRIGATE:
            await hass_api.call_service(
                "frigate",
                "ptz",
                service_data={"action": "preset", "argument": preset},
                target={"entity_id": camera_entity_id},
                return_response=False,
                blocking=True,
            )

        elif method == PTZ_METHOD_ONVIF:
            await hass_api.call_service(
                "onvif",
                "ptz",
                service_data={"move_mode": "GotoPreset", "preset": preset},
                target={"entity_id": camera_entity_id},
                return_response=False,
                blocking=True,
            )
        else:
            _LOGGER.warning("SUPERNOTIFY Unknown PTZ method %s", method)
    except Exception as e:
        _LOGGER.warning("SUPERNOTIFY Unable to move %s to ptz preset %s: %s", camera_entity_id, preset, e)


async def snap_image_entity(
    hass_api: HomeAssistantAPI,
    entity_id: str,
    media_path: Path,
    notification_id: str,
) -> Path | None:
    """Read an image entity and save raw bytes. No reprocessing."""
    raw_path: Path | None = None
    try:
        image_entity: ImageEntity | None = cast("ImageEntity|None", hass_api.domain_entity("image", entity_id))
        if image_entity:
            bitmap: bytes | None = await image_entity.async_image()
            if bitmap:
                raw_dir: Path = Path(media_path) / "raw"
                await raw_dir.mkdir(parents=True, exist_ok=True)
                ext = _detect_image_ext(bitmap)
                raw_path = raw_dir / f"{notification_id}.{ext}"
                async with aiofiles.open(raw_path, "wb") as f:
                    await f.write(bitmap)
    except Exception as e:
        _LOGGER.warning("SUPERNOTIFY Unable to snap image %s: %s", entity_id, e)
    if raw_path is None:
        _LOGGER.warning("SUPERNOTIFY Unable to save from image entity %s", entity_id)
    return raw_path


async def snap_camera(
    hass_api: HomeAssistantAPI,
    camera_entity_id: str,
    notification_id: str,
    media_path: Path,
    max_camera_wait: int = 20,
) -> Path | None:
    """Snap a camera and save the raw image. No reprocessing."""
    if not camera_entity_id:
        _LOGGER.warning("SUPERNOTIFY Empty camera entity id for snap")
        return None

    raw_path: Path | None = None
    try:
        raw_dir: Path = Path(media_path) / "raw"
        await raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"{notification_id}.jpg"
        await hass_api.call_service(
            "camera",
            "snapshot",
            service_data={"entity_id": camera_entity_id, "filename": raw_path},
            return_response=False,
            blocking=True,
        )

        cutoff_time = time.time() + max_camera_wait
        while time.time() < cutoff_time and not await raw_path.exists():
            _LOGGER.info("Image file not available yet at %s, pausing", raw_path)
            await asyncio.sleep(1)

    except Exception as e:
        _LOGGER.warning("Failed to snap avail camera %s to %s: %s", camera_entity_id, raw_path, e)
        raw_path = None

    return raw_path


def camera_available(hass_api: HomeAssistantAPI, camera_config: dict[str, Any], non_entity: bool = False) -> bool:
    state: State | None = None
    tracker_entity_id: str
    camera_entity_id: str = camera_config[CONF_CAMERA]
    try:
        if camera_config.get(CONF_DEVICE_TRACKER):
            tracker_entity_id = camera_config[CONF_DEVICE_TRACKER]
            state = hass_api.get_state(camera_config[CONF_DEVICE_TRACKER])
            if state and state.state == STATE_HOME:
                return True
            _LOGGER.debug("SUPERNOTIFY Skipping camera %s tracker %s state %s", camera_entity_id, tracker_entity_id, state)
        else:
            tracker_entity_id = camera_entity_id
            state = hass_api.get_state(camera_entity_id)
            if state and state.state != STATE_UNAVAILABLE:
                return True
            if state is None and non_entity:
                return True
            _LOGGER.debug("SUPERNOTIFY Skipping camera %s with state %s", camera_entity_id, state)
        if state is None:
            if tracker_entity_id == camera_entity_id:
                _LOGGER.warning(
                    "SUPERNOTIFY Camera %s tracker %s has no entity state",
                    camera_entity_id,
                    tracker_entity_id,
                )
            else:
                _LOGGER.warning(
                    "SUPERNOTIFY Camera %s device_tracker %s seems missing",
                    camera_entity_id,
                    camera_config[CONF_DEVICE_TRACKER],
                )
        return False

    except Exception as e:
        _LOGGER.exception("SUPERNOTIFY Unable to determine camera state: %s, %s", camera_config, e)
        return False


def select_avail_camera(hass_api: HomeAssistantAPI, cameras: dict[str, Any], camera_entity_id: str) -> str | None:
    avail_camera_entity_id: str | None = None

    preferred_cam = cameras.get(camera_entity_id)
    # test support FIXME
    if preferred_cam and CONF_CAMERA not in preferred_cam:
        preferred_cam[CONF_CAMERA] = camera_entity_id
    if preferred_cam is None:
        # assume unconfigured camera available
        return camera_entity_id
    if camera_available(hass_api, preferred_cam):
        return camera_entity_id

    alt_cams: list[dict[str, Any]] = [cameras[c] for c in preferred_cam.get(CONF_ALT_CAMERA, []) if c in cameras]
    alt_cams.extend(
        {CONF_CAMERA: entity_id} for entity_id in preferred_cam.get(CONF_ALT_CAMERA, []) if entity_id not in cameras
    )
    for alt_cam in alt_cams:
        if camera_available(hass_api, alt_cam):
            _LOGGER.info("SUPERNOTIFY Selecting available camera %s rather than %s", alt_cam[CONF_CAMERA], camera_entity_id)
            return alt_cam[CONF_CAMERA]

    if avail_camera_entity_id is None:
        _LOGGER.warning("%s not available, finding best alternative available", camera_entity_id)
        if camera_available(hass_api, preferred_cam, non_entity=True):
            _LOGGER.info("SUPERNOTIFY Selecting camera %s with no known entity", camera_entity_id)
            return camera_entity_id
        for alt_cam in alt_cams:
            if camera_available(hass_api, alt_cam, non_entity=True):
                _LOGGER.info(
                    "SUPERNOTIFY Selecting alt camera %s with no known entity for %s", alt_cam[CONF_CAMERA], camera_entity_id
                )
            return alt_cam[CONF_CAMERA]

    return None


def _detect_image_ext(bitmap: bytes) -> str:
    """Detect image format from raw bytes, returning a file extension."""
    try:
        img = Image.open(io.BytesIO(bitmap))
        fmt = (img.format or "").lower()
        return "jpg" if fmt in ("jpg", "jpeg") else fmt or "img"
    except Exception:
        return "img"


async def snap_notification_image(notification: Notification, context: Context) -> Path | None:  # type: ignore  # noqa: F821
    """Delivery-neutral image acquisition: PTZ movement, camera snap, URL fetch, or image entity.

    Caches the raw image path on notification._raw_image_path. Safe to call multiple times;
    subsequent calls return the cached path immediately.
    """
    if getattr(notification, "_raw_image_path", None) is not None:
        return notification._raw_image_path  # type: ignore[attr-defined]

    if notification.media.get(ATTR_MEDIA_SNAPSHOT_PATH) is not None:
        return Path(notification.media[ATTR_MEDIA_SNAPSHOT_PATH])

    snapshot_url = notification.media.get(ATTR_MEDIA_SNAPSHOT_URL)
    camera_entity_id = notification.media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
    media_path: Path | None = context.media_storage.media_path

    if not media_path or (not snapshot_url and not camera_entity_id):
        return None
    if not context.hass_api:
        return None

    raw_path: Path | None = None
    if snapshot_url:
        raw_path = await snapshot_from_url(
            context.hass_api, snapshot_url, notification.id, media_path, context.hass_api.internal_url
        )
    elif camera_entity_id.startswith("image."):
        raw_path = await snap_image_entity(context.hass_api, camera_entity_id, media_path, notification.id)
    else:
        active_camera_entity_id = select_avail_camera(context.hass_api, context.cameras, camera_entity_id)
        if active_camera_entity_id:
            camera_config = context.cameras.get(active_camera_entity_id, {})
            camera_ptz_entity_id: str = camera_config.get(CONF_PTZ_CAMERA, active_camera_entity_id)
            camera_delay = notification.media.get(ATTR_MEDIA_CAMERA_DELAY, camera_config.get(CONF_PTZ_DELAY))
            camera_ptz_preset_default = camera_config.get(CONF_PTZ_PRESET_DEFAULT)
            camera_ptz_method = camera_config.get(CONF_PTZ_METHOD, PTZ_METHOD_ONVIF)
            camera_ptz_preset = notification.media.get(ATTR_MEDIA_CAMERA_PTZ_PRESET)
            _LOGGER.debug(
                "SUPERNOTIFY snapping camera %s, ptz %s->%s (%s), delay %s secs",
                active_camera_entity_id,
                camera_ptz_preset,
                camera_ptz_preset_default,
                camera_ptz_entity_id,
                camera_delay,
            )
            if camera_ptz_preset:
                await move_camera_to_ptz_preset(
                    context.hass_api, camera_ptz_entity_id, camera_ptz_preset, method=camera_ptz_method
                )
            if camera_delay:
                _LOGGER.debug("SUPERNOTIFY Waiting %s secs before snapping", camera_delay)
                await asyncio.sleep(camera_delay)
            raw_path = await snap_camera(
                context.hass_api, active_camera_entity_id, notification.id, media_path=media_path, max_camera_wait=15
            )
            if camera_ptz_preset and camera_ptz_preset_default:
                await move_camera_to_ptz_preset(
                    context.hass_api, camera_ptz_entity_id, camera_ptz_preset_default, method=camera_ptz_method
                )

    if raw_path is None:
        _LOGGER.warning("SUPERNOTIFY No media available to attach (%s,%s)", snapshot_url, camera_entity_id)
    notification._raw_image_path = raw_path  # type: ignore[attr-defined]
    return raw_path


async def grab_image(notification: Notification, delivery: Delivery, context: Context) -> Path | None:  # type: ignore  # noqa: F821
    """Get a delivery-ready image, reprocessing the raw snap with delivery-specific settings.

    The raw snap is cached on the notification; reprocessed variants are cached by filename
    so multiple deliveries with the same settings share the processed file.

    Filename convention:
      raw/{nid}.{ext}                  — delivery-neutral camera output
      image/{nid}.jpg                  — default reprocessing (ALWAYS, no extra opts)
      image/{nid}_{hashed_opts}}.jpg   — delivery-specific opts or non-ALWAYS reprocess mode
    """
    if notification.media.get(ATTR_MEDIA_SNAPSHOT_PATH) is not None:
        return Path(notification.media[ATTR_MEDIA_SNAPSHOT_PATH])

    raw_path = await snap_notification_image(notification, context)
    if raw_path is None:
        return None

    media_path: Path | None = context.media_storage.media_path
    if not media_path or not context.hass_api:
        return None

    delivery_config = notification.delivery_data(delivery)
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

    if reprocess == ReprocessOption.NEVER:
        return raw_path

    raw_ext = raw_path.suffix.lstrip(".").lower()
    relevant_opts: dict[str, Any] = jpeg_opts if raw_ext in ("jpg", "jpeg") else png_opts if raw_ext == "png" else {}
    is_default = not relevant_opts and reprocess == ReprocessOption.ALWAYS
    if is_default:
        processed_name = f"{notification.id}.jpg"
    else:
        key = hex(hash((reprocess_option, *tuple(relevant_opts.values()))))[-12:]
        processed_name = f"{notification.id}_{key}.jpg"
    processed_path = Path(media_path) / "image" / processed_name

    if await processed_path.exists():
        return await processed_path.resolve()

    async with await raw_path.open("rb") as f:
        bitmap: bytes = await f.read()
    return await write_image_from_bitmap(
        context.hass_api, bitmap, processed_path, reprocess=reprocess, jpeg_opts=jpeg_opts, png_opts=png_opts
    )


async def write_image_from_bitmap(
    hass_api: HomeAssistantAPI,
    bitmap: bytes | None,
    output_path: Path,
    reprocess: ReprocessOption = ReprocessOption.ALWAYS,
    output_format: str | None = None,
    jpeg_opts: dict[str, Any] | None = None,
    png_opts: dict[str, Any] | None = None,
) -> Path | None:
    """Reprocess a raw image bitmap and write to an explicit output path."""
    if bitmap is None:
        _LOGGER.debug("SUPERNOTIFY Empty bitmap for image")
        return None
    input_format: str = "img"
    try:
        await output_path.parent.mkdir(parents=True, exist_ok=True)

        image = await hass_api.create_job(Image.open, io.BytesIO(bitmap))

        input_format = image.format.lower() if image.format else "img"
        if reprocess == ReprocessOption.ALWAYS:
            # rewrite to remove metadata, incl custom CCTV comments that confuse python MIMEImage
            clean_image: Image.Image = Image.new(image.mode, image.size)
            clean_image.putdata(image.getdata())  # being removed in 2027
            # clean_image.putdata(image.get_flattened_data()) # added in jan 2026
            image = clean_image

        buffer = BytesIO()
        img_args: dict[str, Any] = {}
        if reprocess in (ReprocessOption.ALWAYS, ReprocessOption.PRESERVE):
            if input_format in ("jpg", "jpeg") and jpeg_opts:
                img_args.update(jpeg_opts)
            elif input_format == "png" and png_opts:
                img_args.update(png_opts)

        image.save(buffer, output_format or input_format, **img_args)

        output_path = await output_path.resolve()
        async with aiofiles.open(output_path, "wb") as file:
            await file.write(buffer.getbuffer())
        return output_path
    except TypeError:
        # probably a jpeg or png option
        _LOGGER.exception("SUPERNOTIFY Image snap fail")
    except Exception:
        _LOGGER.exception("SUPERNOTIFY Failure saving %s bitmap", input_format)
    return None


class MediaStorage:
    def __init__(self, media_path: str | None, media_url_prefix: str | None = None, days: int = 7) -> None:
        self.media_path: Path | None = Path(media_path) if media_path else None
        self.last_purge: dt.datetime | None = None
        self.media_url_prefix = media_url_prefix
        self.purge_minute_interval = 60 * 6
        self.days = days

    async def initialize(self, hass_api: HomeAssistantAPI) -> None:
        self.hass_api = hass_api  # TODO: should not be set on initialize
        if self.media_path is not None and not self.media_path.is_absolute():
            self.media_path = await self.media_path.absolute()
            _LOGGER.info("SUPERNOTIFY media path updated to %s", self.media_path)
        if self.media_path and not await self.media_path.exists():
            _LOGGER.info("SUPERNOTIFY media path not found at %s", self.media_path)
            try:
                await self.media_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY media path %s cannot be created: %s", self.media_path, e)
                hass_api.raise_issue(
                    "media_path",
                    "media_path",
                    {"path": str(self.media_path), "error": str(e)},
                    learn_more_url="https://supernotify.rhizomatics.org.uk/#getting-started",
                )
                self.media_path = None
        if self.media_path is not None:
            _LOGGER.info("SUPERNOTIFY abs media path: %s", await self.media_path.absolute())

        if self.media_url_prefix is not None:
            await hass_api.register_web_path(self.media_path, self.media_url_prefix)

    async def object_url(self, relative_path: Path) -> str | None:
        """Convert a local image path to an externally accessible URL via the registered static path."""
        if not self.media_url_prefix or self.media_path is None:
            return None
        try:
            relative = relative_path.relative_to(await self.media_path.absolute())
            return self.hass_api.abs_url(f"{self.media_url_prefix}/{relative}")
        except ValueError as e:
            _LOGGER.warning("SUPERNOTIFY Invalid media path for URL %s: %s", relative_path, e)
            return None

    async def size(self) -> int:
        path: Path | None = self.media_path
        if path and await path.exists():
            return sum(1 for p in await aiofiles.os.listdir(path))
        return 0

    async def cleanup(self, days: int | None = None, force: bool = False) -> int:
        if (
            not force
            and self.last_purge is not None
            and self.last_purge > dt.datetime.now(dt.UTC) - dt.timedelta(minutes=self.purge_minute_interval)
        ):
            return 0
        days = days or self.days
        if days == 0 or self.media_path is None:
            return 0

        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
        cutoff = cutoff.astimezone(dt.UTC)
        purged = 0
        if self.media_path and await self.media_path.exists():
            try:
                archive = await aiofiles.os.scandir(self.media_path)
                for entry in archive:
                    if entry.is_file() and dt_util.utc_from_timestamp(entry.stat().st_ctime) <= cutoff:
                        _LOGGER.debug("SUPERNOTIFY Purging %s", entry.path)
                        await aiofiles.os.unlink(Path(entry.path))
                        purged += 1
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to clean up media storage at %s: %s", self.media_path, e, exc_info=True)
            _LOGGER.info("SUPERNOTIFY Purged %s media storage for cutoff %s", purged, cutoff)
            self.last_purge = dt.datetime.now(dt.UTC)
        else:
            _LOGGER.debug("SUPERNOTIFY Skipping media storage for unknown path %s", self.media_path)
        return purged
