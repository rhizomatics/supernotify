"""Gotify transport for SuperNotify.

Sends push notifications via Gotify (self-hosted, privacy-first push server).
Requires the HACS custom integration 1RandomDev/homeassistant-gotify installed
and configured in configuration.yaml. The notify service name (e.g. notify.gotify)
depends on the user's HACS configuration - it MUST be specified as `action:` in
delivery.yaml (no default exists).

Prerequisites:
    - Gotify server running and reachable
    - HACS integration 1RandomDev/homeassistant-gotify installed
    - Application token configured in configuration.yaml
    - `action: notify.<name>` set in delivery.yaml (REQUIRED)

For snapshot camera / bigImageUrl:
    - `media_web_path` must be configured (PLATFORM_SCHEMA) for grab_image to produce a URL.
    - `external_url` must be configured in HA for the URL to be reachable outside the local network.

Supported data: keys (all optional):
    gotify_priority     int (0-10)  Override priority (0=silent ... 10=max).
                                    Accepts string "7" -> cast to int.
                                    Out-of-range values are clamped.
    gotify_click        str (URL)   URL opened on tap of the notification.
    gotify_image_url    str (URL)   Direct URL for bigImageUrl (expanded image).
                                    Takes precedence over gotify_attach_image.
    gotify_attach_image bool        Grab image via shared pipeline and use as bigImageUrl.
                                    Used only when no snapshot_url is already in media.
                                    Requires media_web_path configured and image saved within it.
    gotify_markdown     bool        Enable Markdown rendering (text/markdown).
                                    Accepts "true"/"false" YAML strings safely.
    gotify_intent_url   str (URL)   Android intent URL on message receive.
                                    Requires "Intent Action Permission" in Gotify app.

Priority mapping (SuperNotify -> Gotify integer):
    critical -> 10    high -> 7    medium -> 5    low -> 2    minimum -> 0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify.const import ATTR_DATA

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import (
    ATTR_MEDIA_SNAPSHOT_URL,
    TRANSPORT_GOTIFY,
)
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

_PRIORITY_MAP: dict[str, int] = {
    "critical": 10,
    "high": 7,
    "medium": 5,
    "low": 2,
    "minimum": 0,
}


def _build_extras(
    click_url: str | None,
    image_url: str | None,
    markdown: bool,
    intent_url: str | None,
) -> dict | None:
    """Build Gotify extras dict. Returns None if no extras are needed."""
    extras: dict = {}

    client_notification: dict = {}
    if click_url:
        client_notification["click"] = {"url": click_url}
    if image_url:
        client_notification["bigImageUrl"] = image_url
    if client_notification:
        extras["client::notification"] = client_notification

    if markdown:
        extras["client::display"] = {"contentType": "text/markdown"}

    if intent_url:
        extras["android::action"] = {"onReceive": {"intentUrl": intent_url}}

    return extras if extras else None


class GotifyTransport(Transport):
    """Notify via Gotify self-hosted push notification server."""

    name = TRANSPORT_GOTIFY

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE | TransportFeature.IMAGES | TransportFeature.SNAPSHOT_IMAGE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.target_required = TargetRequired.NEVER
        # No default action - user MUST specify action: notify.<name> in delivery.yaml
        return config

    def validate_action(self, action: str | None) -> bool:
        if action and action.startswith("notify."):
            return True
        _LOGGER.warning(
            "SUPERNOTIFY gotify: action must be a notify.* service (e.g. notify.gotify), got: %r",
            action,
        )
        return False

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY gotify %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # --- Extract gotify_* keys (must not reach the notify service) ---
        priority_ovr_raw = raw_data.pop("gotify_priority", None)
        click_url = raw_data.pop("gotify_click", None)
        image_url: str | None = raw_data.pop("gotify_image_url", None)
        attach_image = boolify(raw_data.pop("gotify_attach_image", False), default=False)
        markdown = boolify(raw_data.pop("gotify_markdown", False), default=False)
        intent_url = raw_data.pop("gotify_intent_url", None)

        # --- Priority: validate override or use auto-mapping ---
        priority_ovr: int | None = None
        if priority_ovr_raw is not None:
            try:
                priority_ovr = int(priority_ovr_raw)
                if not 0 <= priority_ovr <= 10:
                    _LOGGER.warning(
                        "SUPERNOTIFY gotify: gotify_priority %d out of range 0-10, clamping",
                        priority_ovr,
                    )
                    priority_ovr = max(0, min(10, priority_ovr))
            except (TypeError, ValueError) as e:  # py3.13 compat
                _LOGGER.warning("SUPERNOTIFY gotify: invalid gotify_priority %r, using auto mapping: %s", priority_ovr_raw, e)
                priority_ovr = None

        gotify_priority: int = priority_ovr if priority_ovr is not None else _PRIORITY_MAP.get(envelope.priority or "medium", 5)

        # --- Base action data ---
        action_data = envelope.core_action_data()

        # --- Resolve image_url (bigImageUrl): explicit > snapshot_url > grab_image ---
        if not image_url and envelope.media:
            snapshot_url = envelope.media.get(ATTR_MEDIA_SNAPSHOT_URL)
            if snapshot_url:
                image_url = self.hass_api.abs_url(snapshot_url)
            elif attach_image:
                image_path = await envelope.grab_image()
                if image_path:
                    image_url = await self.context.media_storage.object_url(image_path)

        # --- Build nested payload_data ---
        payload_data: dict[str, Any] = {"priority": gotify_priority}

        extras = _build_extras(click_url, image_url, markdown, intent_url)
        if extras:
            payload_data["extras"] = extras

        action_data[ATTR_DATA] = payload_data

        # raw_data residuo non passato - schema HACS e' fisso
        return await self.call_action(envelope, action_data=action_data)
