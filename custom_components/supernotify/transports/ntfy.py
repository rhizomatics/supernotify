"""ntfy transport for SuperNotify.

Sends push notifications via ntfy (https://ntfy.sh) or self-hosted instance.
ntfy is an official HA integration since 2025.5.
Uses ntfy.publish action with device_id target (topics configured in HA integration).

Supported data: keys (all optional except ntfy_device_id):
    ntfy_device_id   str         device_id of the ntfy topic configured in HA (required)
    ntfy_priority    int         5=urgent, 4=high, 3=default, 2=low, 1=min
    ntfy_tags        list[str]   tag/emoji shortcodes (e.g. ["warning", "house"])
    ntfy_click       str         URL opened on notification tap
    ntfy_attach_image bool       grab image via shared pipeline and attach to ntfy.
                                 Used only when no snapshot_url is already in media.
                                 Requires media_web_path configured and image saved within it.
    ntfy_filename    str         attachment filename (default: snapshot.jpg)
    ntfy_icon        str         JPEG/PNG icon URL
    ntfy_markdown    bool        enable Markdown rendering (default: false)
    ntfy_delay       str         delivery delay: "10m", "1h", "2h30m", or "HH:MM"
    ntfy_sequence_id str         message ID for subsequent updates/cancellations
    ntfy_email       str         email forwarding (e.g. "user@example.com")
    ntfy_actions     list[dict]  action buttons, max 3 (see examples below)

ntfy_actions -- supported types:
    view:      {action: view, label: "Open", url: "https://...", clear: false}
    http:      {action: http, label: "POST", url: "https://...", method: post, headers: {}, body: ""}
    broadcast: {action: broadcast, label: "Intent", intent: "io.heckel.ntfy.USER_ACTION", extras: {}}
    copy:      {action: copy, label: "Copy", value: "text to copy"}
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_DEVICE_ID

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import (
    ATTR_MEDIA_SNAPSHOT_URL,
    TRANSPORT_NTFY,
)
from custom_components.supernotify.model import DebugTrace, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

_PRIORITY_MAP = {
    "critical": 5,  # urgent/max
    "high": 4,  # high
    "medium": 3,  # default
    "low": 2,  # low
    "minimum": 1,  # min
}

_DELAY_RE = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")

_REQUIRED_ACTION_KEYS = {"action", "label"}


def _parse_delay(delay: str) -> str:
    """Convert user-friendly delay to HA offset format HH:MM or HH:MM:SS.

    Accepts: "10m", "1h", "1h30m", "00:10", "01:30:00"
    Returns: "HH:MM" or "HH:MM:SS"
    """
    if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", delay):
        return delay  # already in HH:MM or HH:MM:SS format
    m = _DELAY_RE.fullmatch(delay.strip())
    if m and (m.group(1) or m.group(2) or m.group(3)):
        hours = int(m.group(1) or 0)
        minutes = int(m.group(2) or 0)
        seconds = int(m.group(3) or 0)
        if seconds:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{hours:02d}:{minutes:02d}"
    _LOGGER.warning("SUPERNOTIFY ntfy: unrecognized delay format '%s', passing as-is", delay)
    return delay


def _validate_actions(actions: list) -> list:
    """Validate ntfy action buttons, dropping malformed entries with a warning."""
    valid = []
    for i, a in enumerate(actions):
        if not isinstance(a, dict) or not _REQUIRED_ACTION_KEYS.issubset(a):
            missing = _REQUIRED_ACTION_KEYS - set(a) if isinstance(a, dict) else _REQUIRED_ACTION_KEYS
            _LOGGER.warning(
                "SUPERNOTIFY ntfy: action[%d] missing required keys %s, skipped",
                i,
                missing,
            )
            continue
        valid.append(a)
    return valid


class NtfyTransport(Transport):
    """Notify via ntfy push notification service."""

    name = TRANSPORT_NTFY

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return (
            TransportFeature.MESSAGE
            | TransportFeature.TITLE
            | TransportFeature.IMAGES
            | TransportFeature.ACTIONS
            | TransportFeature.SNAPSHOT_IMAGE
        )

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "ntfy.publish"
        config.delivery_defaults.target_required = TargetRequired.NEVER
        return config

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY ntfy %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        device_id = raw_data.pop("ntfy_device_id", None)
        priority_ovr = raw_data.pop("ntfy_priority", None)
        tags = raw_data.pop("ntfy_tags", [])
        click_url = raw_data.pop("ntfy_click", None)
        attach_image = boolify(raw_data.pop("ntfy_attach_image", False), default=False)
        filename = raw_data.pop("ntfy_filename", "snapshot.jpg")
        icon = raw_data.pop("ntfy_icon", None)
        markdown = boolify(raw_data.pop("ntfy_markdown", False), default=False)
        delay = raw_data.pop("ntfy_delay", None)
        sequence_id = raw_data.pop("ntfy_sequence_id", None)
        email = raw_data.pop("ntfy_email", None)
        actions = raw_data.pop("ntfy_actions", [])

        if not device_id:
            _LOGGER.warning("SUPERNOTIFY ntfy: ntfy_device_id not configured in delivery data")
            return False

        # Validate ntfy_priority range (1-5)
        if priority_ovr is not None:
            try:
                priority_ovr = int(priority_ovr)
                if not 1 <= priority_ovr <= 5:
                    _LOGGER.warning("SUPERNOTIFY ntfy: ntfy_priority %s out of range 1-5, using mapping", priority_ovr)
                    priority_ovr = None
            except (TypeError, ValueError) as e:  # py3.13 compat
                _LOGGER.warning("SUPERNOTIFY ntfy: invalid ntfy_priority %r, using mapping: %s", priority_ovr, e)
                priority_ovr = None

        ntfy_priority = priority_ovr or _PRIORITY_MAP.get(envelope.priority or "medium", 3)

        action_data = envelope.core_action_data()
        action_data["priority"] = ntfy_priority

        if tags:
            action_data["tags"] = tags
        if click_url:
            action_data["click"] = click_url
        if icon:
            action_data["icon"] = icon
        if markdown:
            action_data["markdown"] = True
        if delay:
            action_data["delay"] = _parse_delay(delay)
        if sequence_id:
            action_data["sequence_id"] = sequence_id
        if email:
            action_data["email"] = email
        if actions:
            if not isinstance(actions, list):
                _LOGGER.warning("SUPERNOTIFY ntfy: ntfy_actions must be a list, ignored")
            else:
                action_data["actions"] = _validate_actions(actions)[:3]

        # Image attachment: snapshot_url passthrough > grab_image for camera
        if envelope.media:
            snapshot_url = envelope.media.get(ATTR_MEDIA_SNAPSHOT_URL)
            if snapshot_url:
                action_data["attach"] = self.hass_api.abs_url(snapshot_url)
                action_data["filename"] = filename
            elif attach_image:
                image_path = await envelope.grab_image()
                if image_path:
                    image_url = await self.context.media_storage.object_url(image_path)
                    if image_url:
                        action_data["attach"] = image_url
                        action_data["filename"] = filename

        # Residual generic keys (non ntfy_*) passed to payload
        action_data.update(raw_data)

        target_data = {ATTR_DEVICE_ID: device_id}

        return await self.call_action(envelope, action_data=action_data, target_data=target_data)
