"""Pushover transport for SuperNotify.

Sends push notifications via Pushover (https://pushover.net).
Requires the official HA Pushover integration configured in configuration.yaml:

    notify:
      - name: pushover_home
        platform: pushover
        api_key: YOUR_PUSHOVER_API_KEY
        user_key: YOUR_PUSHOVER_USER_KEY

The notify service name (e.g. notify.pushover_home) MUST be specified as
`action:` in delivery.yaml — there is no default, since the name depends on
the user's configuration.yaml entry.

Priority mapping (SuperNotify -> Pushover integer):
    critical -> 2  (emergency: requires retry+expire, repeats until acknowledged)
    high     -> 1  (high: bypasses user's quiet hours)
    medium   -> 0  (normal: standard sound and vibration)
    low      -> -1 (low: no sound and no vibration)
    minimum  -> -2 (silent: only iOS badge, no visible notification)

Note on emergency (priority=2): Pushover REQUIRES the `retry` and `expire`
parameters. If not provided, SuperNotify supplies sensible defaults
(retry=60s, expire=3600s) and logs them.

Supported data keys (all optional unless noted):
    pushover_priority   int (-2..2)  Override priority; out-of-range -> auto-mapping.
    pushover_sound      str          Notification sound: "pushover", "bike", "siren",
                                     "vibrate", "none", "alien", "echo", etc.
                                     See https://pushover.net/api#sounds
    pushover_url        str          Supplementary URL attached to the notification.
    pushover_url_title  str          Title for the URL (max 100 chars).
    pushover_retry      int          Seconds between retries (min 30, default 60).
                                     Emergency only (priority=2).
    pushover_expire     int          Total seconds to keep retrying (max 10800,
                                     default 3600). Emergency only.
    pushover_callback   str          Public URL for emergency acknowledgment webhook
                                     (HA webhook endpoint).
    pushover_html       bool         Enable HTML formatting in the message
                                     (links, bold, italic). Default: false.
    pushover_ttl        int          Seconds before automatic deletion of the
                                     notification from the device.
    pushover_device     str          Send to a specific device (device name as
                                     configured in Pushover, e.g. "iphone").
                                     Default: all devices on the account.
    pushover_attach_image bool       Grab camera snapshot (uses
                                     media.camera_entity_id from the SuperNotify
                                     call) and attach it to the notification.
                                     Requires TransportFeature.SNAPSHOT_IMAGE.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_DATA

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import TRANSPORT_PUSHOVER
from custom_components.supernotify.model import (
    DebugTrace,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

# SuperNotify priority -> Pushover integer (-2..2)
_PRIORITY_MAP: dict[str, int] = {
    "critical": 2,  # emergency - repeats until acknowledged, requires retry+expire
    "high": 1,  # high - bypasses user quiet hours
    "medium": 0,  # normal - standard sound and vibration
    "low": -1,  # low - no sound and no vibration
    "minimum": -2,  # silent - only iOS badge, no visible notification
}

_EMERGENCY_PRIORITY = 2
_EMERGENCY_RETRY_MIN = 30  # seconds (Pushover API limit)
_EMERGENCY_EXPIRE_MAX = 10800  # seconds (Pushover API limit = 3 hours)
_EMERGENCY_RETRY_DEFAULT = 60  # sensible default when not specified
_EMERGENCY_EXPIRE_DEFAULT = 3600  # sensible default when not specified (1 hour)


class PushoverTransport(Transport):
    """Notify via Pushover push notification service."""

    name = TRANSPORT_PUSHOVER

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE | TransportFeature.IMAGES | TransportFeature.SNAPSHOT_IMAGE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.target_required = TargetRequired.NEVER
        # No default action — user MUST specify action: notify.<name> in delivery.yaml
        return config

    def validate_action(self, action: str | None) -> bool:
        if action and action.startswith("notify."):
            return True
        _LOGGER.warning(
            "SUPERNOTIFY pushover: action must be a notify.* service (e.g. notify.pushover_home), got: %r",
            action,
        )
        return False

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY pushover %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # --- Pop pushover_* keys (must not be forwarded to the service) ---
        priority_ovr_raw = raw_data.pop("pushover_priority", None)
        sound = raw_data.pop("pushover_sound", None)
        url = raw_data.pop("pushover_url", None)
        url_title = raw_data.pop("pushover_url_title", None)
        retry_raw = raw_data.pop("pushover_retry", None)
        expire_raw = raw_data.pop("pushover_expire", None)
        callback = raw_data.pop("pushover_callback", None)
        html_flag = boolify(raw_data.pop("pushover_html", False), default=False)
        ttl_raw = raw_data.pop("pushover_ttl", None)
        device = raw_data.pop("pushover_device", None)
        attach_image = boolify(raw_data.pop("pushover_attach_image", False), default=False)

        # --- Priority: validate override or use auto-mapping ---
        priority_ovr: int | None = None
        if priority_ovr_raw is not None:
            try:
                priority_ovr = int(priority_ovr_raw)
                if not -2 <= priority_ovr <= 2:
                    _LOGGER.warning(
                        "SUPERNOTIFY pushover: pushover_priority %d out of range -2..2, falling back to auto mapping",
                        priority_ovr,
                    )
                    priority_ovr = None
            except (TypeError, ValueError):  # py3.13 compat
                _LOGGER.warning(
                    "SUPERNOTIFY pushover: invalid pushover_priority %r, falling back to auto mapping",
                    priority_ovr_raw,
                )
                priority_ovr = None

        pushover_priority: int = (
            priority_ovr if priority_ovr is not None else _PRIORITY_MAP.get(envelope.priority or "medium", 0)
        )

        # --- Base action data (includes message and title) ---
        action_data = envelope.core_action_data()

        # --- Pushover-specific data payload ---
        push_data: dict[str, Any] = {"priority": pushover_priority}

        # Emergency (priority=2): Pushover REQUIRES retry and expire
        if pushover_priority == _EMERGENCY_PRIORITY:
            # retry: robust parse (YAML string or int) -> fallback default on error
            if retry_raw is None:
                retry_val: int = _EMERGENCY_RETRY_DEFAULT
            else:
                try:
                    retry_val = int(retry_raw)
                except (TypeError, ValueError):
                    _LOGGER.warning(
                        "SUPERNOTIFY pushover: invalid pushover_retry %r, using default %ds",
                        retry_raw,
                        _EMERGENCY_RETRY_DEFAULT,
                    )
                    retry_val = _EMERGENCY_RETRY_DEFAULT

            # expire: same robust pattern
            if expire_raw is None:
                expire_val: int = _EMERGENCY_EXPIRE_DEFAULT
            else:
                try:
                    expire_val = int(expire_raw)
                except (TypeError, ValueError):
                    _LOGGER.warning(
                        "SUPERNOTIFY pushover: invalid pushover_expire %r, using default %ds",
                        expire_raw,
                        _EMERGENCY_EXPIRE_DEFAULT,
                    )
                    expire_val = _EMERGENCY_EXPIRE_DEFAULT

            if retry_val < _EMERGENCY_RETRY_MIN:
                _LOGGER.warning(
                    "SUPERNOTIFY pushover: emergency retry %ds < minimum %ds, clamping",
                    retry_val,
                    _EMERGENCY_RETRY_MIN,
                )
                retry_val = _EMERGENCY_RETRY_MIN

            if expire_val > _EMERGENCY_EXPIRE_MAX:
                _LOGGER.warning(
                    "SUPERNOTIFY pushover: emergency expire %ds > maximum %ds, clamping",
                    expire_val,
                    _EMERGENCY_EXPIRE_MAX,
                )
                expire_val = _EMERGENCY_EXPIRE_MAX

            push_data["retry"] = retry_val
            push_data["expire"] = expire_val

            if callback:
                push_data["callback"] = callback

            _LOGGER.debug(
                "SUPERNOTIFY pushover: emergency mode - retry=%ds expire=%ds",
                retry_val,
                expire_val,
            )

        # Optional fields - added only when present
        if sound:
            push_data["sound"] = sound
        if url:
            push_data["url"] = url
        if url_title:
            push_data["url_title"] = url_title
        if html_flag:
            push_data["html"] = 1
        if ttl_raw is not None:
            try:
                push_data["ttl"] = int(ttl_raw)
            except (TypeError, ValueError):
                _LOGGER.warning("SUPERNOTIFY pushover: invalid pushover_ttl %r, ignored", ttl_raw)
        if device:
            push_data["device"] = device

        # --- Camera image attachment via envelope.grab_image() (v1.14.0+) ---
        if attach_image:
            try:
                image_path = await envelope.grab_image()
                if image_path:
                    push_data["attachment"] = str(image_path)
                    _LOGGER.debug("SUPERNOTIFY pushover: attaching image %s", image_path)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY pushover: failed to grab image: %s", e)

        action_data[ATTR_DATA] = push_data

        # Remaining raw_data is NOT forwarded - Pushover HA service schema is fixed
        return await self.call_action(envelope, action_data=action_data)
