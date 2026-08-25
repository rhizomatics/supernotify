"""Kodi transport for SuperNotify.

Shows on-screen overlay notifications on Kodi media centers using Home
Assistant's `kodi` integration, calling the entity-based `kodi.call_method`
service with the JSON-RPC method `GUI.ShowNotification`.

Supported data keys (all optional):
    kodi_displaytime    int     overlay duration in milliseconds
                                (default: 10000). Kodi enforces a minimum
                                of 1500 ms, lower values are clamped.
    kodi_icon           str     "info" | "warning" | "error" or an image
                                URL. Overrides the priority-derived icon.
    kodi_attach_image   bool    use the camera snapshot as the notification
                                icon, resolved to a URL reachable from the
                                Kodi host (default: False). When an image
                                URL is resolved it wins over kodi_icon.

Priority to native icon mapping (when kodi_icon is not set):
    critical -> "error", high -> "warning",
    medium / low / minimum -> "info"

Notes on the `kodi.call_method` service:
- The service is entity-based: Kodi instances are `media_player` entities
  created by the kodi config entry. Targets are pre-filtered here to
  `media_player.*` entity ids and passed via target_data; other targets
  are dropped with a debug log.
- `GUI.ShowNotification` requires a non-empty `title`: when the envelope
  has no title, a "Notification" fallback is used.
- Kodi runs on a remote host, so the snapshot image must be a URL that the
  Kodi box can fetch, NEVER a local HA filesystem path. Resolution order:
  1. `envelope.media[snapshot_url]` (absolutised against the HA base URL)
  2. `envelope.grab_image()` + `media_storage.object_url()` (already an
     absolute URL served by the HA web server)
  The HA Internal URL should be a direct IP (e.g. http://192.168.0.123:8123)
  rather than an mDNS `.local` hostname, which some players cannot resolve.
- No residual data passthrough: any extra key in the payload is forwarded
  by `kodi.call_method` as a JSON-RPC parameter and makes the whole
  `GUI.ShowNotification` call fail on the Kodi side. Residual generic data
  keys are therefore dropped with a debug log, unlike the standard
  transport pattern.
- Pure overlay: no action buttons and no user interaction.

Internal data keys filtered upstream by notification.py and NOT popped here:
    force_resend, spoken_message

References:
- Kodi integration: https://www.home-assistant.io/integrations/kodi/
- JSON-RPC GUI.ShowNotification: https://kodi.wiki/view/JSON-RPC_API

"""

from __future__ import annotations

import logging
import re
import urllib.parse
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import (
    ATTR_MEDIA_SNAPSHOT_URL,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_SELECT,
    TRANSPORT_KODI,  # added via const_additions_kodi.py
)
from custom_components.supernotify.model import DebugTrace, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

RE_VALID_KODI = r"media_player\.[A-Za-z0-9_]+"

_KODI_ENTITY_RE = re.compile(rf"^{RE_VALID_KODI}$")

# GUI.ShowNotification displaytime constraints (milliseconds)
DEFAULT_DISPLAYTIME = 10000
MIN_DISPLAYTIME = 1500

# GUI.ShowNotification requires a non-empty title
DEFAULT_TITLE = "Notification"

# SuperNotify priority -> Kodi native notification icon
_PRIORITY_ICON = {
    "critical": "error",
    "high": "warning",
    "medium": "info",
    "low": "info",
    "minimum": "info",
}
_DEFAULT_ICON = "info"


def _coerce_int(value: Any) -> int | None:
    """Best-effort int coercion. Returns None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


class KodiTransport(Transport):
    """Notify via Kodi on-screen overlay using the kodi integration."""

    name = TRANSPORT_KODI

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE | TransportFeature.IMAGES | TransportFeature.SNAPSHOT_IMAGE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "kodi.call_method"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        config.delivery_defaults.options = {
            OPTION_TARGET_SELECT: [RE_VALID_KODI],
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
        }
        return config

    def validate_action(self, action: str | None) -> bool:
        """Validate that action is the kodi call_method service."""
        return action == "kodi.call_method"

    def select_targets(self, envelope: Envelope) -> list[str]:
        """Filter envelope targets down to media_player entity ids.

        `kodi.call_method` only accepts media_player entities; anything else
        is dropped with a debug log. Duplicates are removed preserving order.
        """
        raw_targets: list[str] = envelope.target.entity_ids or [] if envelope.target else []
        targets: list[str] = []
        for target in raw_targets:
            if isinstance(target, str) and _KODI_ENTITY_RE.match(target):
                if target not in targets:
                    targets.append(target)
            else:
                _LOGGER.debug("SUPERNOTIFY kodi: skipping invalid target %r", target)
        return targets

    def _absolute_url(self, url: str) -> str:
        """Make a relative URL absolute so the Kodi host can fetch it.

        Prefers the HA internal URL since Kodi is typically a LAN device;
        falls back to the external URL. Absolute URLs pass through as-is.
        """
        if not url or url.startswith(("http://", "https://")):
            return url
        base = self.hass_api.internal_url or self.hass_api.external_url
        if not base:
            _LOGGER.warning("SUPERNOTIFY kodi: no base url to absolutise %s", url)
            return url
        if not url.startswith("/"):
            url = "/" + url
        return urllib.parse.urljoin(base, url)

    async def _resolve_image_url(self, envelope: Envelope) -> str | None:
        """Resolve a snapshot image URL reachable from the Kodi host.

        Order of resolution:
          1. envelope.media snapshot_url (absolutised against HA base URL)
          2. envelope.grab_image() + media_storage.object_url() (served by
             the HA web server via the registered media path)
          3. None (caller keeps the priority/override icon)
        """
        snapshot_url = envelope.media.get(ATTR_MEDIA_SNAPSHOT_URL) if envelope.media else None
        if snapshot_url:
            return self._absolute_url(str(snapshot_url))

        image_path = None
        try:
            image_path = await envelope.grab_image()
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY kodi: failed to grab image: %s", e)
        if image_path:
            try:
                object_url = await self.context.media_storage.object_url(image_path)
            except Exception as e:
                _LOGGER.debug("SUPERNOTIFY kodi: object_url failed for %s: %s", image_path, e)
                object_url = None
            if object_url:
                return object_url
            _LOGGER.debug("SUPERNOTIFY kodi: no shareable URL for %s, image skipped", image_path)
        return None

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY kodi %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # Pop Kodi-specific data keys
        displaytime_raw = raw_data.pop("kodi_displaytime", None)
        icon_override = raw_data.pop("kodi_icon", None)
        attach_image = boolify(raw_data.pop("kodi_attach_image", False), default=False)

        # Resolve and pre-validate media_player targets
        targets = self.select_targets(envelope)
        if not targets:
            _LOGGER.warning("SUPERNOTIFY kodi: no valid media_player targets")
            self.record_error("no valid Kodi media_player targets", "deliver")
            return False

        # Coerce displaytime and clamp to the Kodi minimum
        displaytime = _coerce_int(displaytime_raw)
        if displaytime is None:
            if displaytime_raw is not None:
                _LOGGER.warning(
                    "SUPERNOTIFY kodi: invalid kodi_displaytime %r, using default %d ms",
                    displaytime_raw,
                    DEFAULT_DISPLAYTIME,
                )
            displaytime = DEFAULT_DISPLAYTIME
        if displaytime < MIN_DISPLAYTIME:
            _LOGGER.debug(
                "SUPERNOTIFY kodi: kodi_displaytime %d below Kodi minimum, clamping to %d ms",
                displaytime,
                MIN_DISPLAYTIME,
            )
            displaytime = MIN_DISPLAYTIME

        # Icon: priority-derived default, then kodi_icon override, then
        # snapshot image URL (which wins when resolvable)
        icon: str = _PRIORITY_ICON.get(envelope.priority or "medium", _DEFAULT_ICON)
        if icon_override:
            icon = str(icon_override)
        if attach_image:
            image_url = await self._resolve_image_url(envelope)
            if image_url:
                icon = image_url
            else:
                _LOGGER.debug("SUPERNOTIFY kodi: no image URL available, keeping icon %r", icon)

        # Build the JSON-RPC payload. Every key in action_data beyond
        # `method` is forwarded as a GUI.ShowNotification parameter, so
        # residual generic data keys are NOT merged: an unknown parameter
        # fails the whole JSON-RPC call on the Kodi side.
        action_data: dict[str, Any] = {
            "method": "GUI.ShowNotification",
            "title": envelope.title or DEFAULT_TITLE,
            "message": envelope.message or "",
            "image": icon,
            "displaytime": displaytime,
        }

        if raw_data:
            _LOGGER.debug(
                "SUPERNOTIFY kodi: dropping data keys not supported by GUI.ShowNotification: %s",
                sorted(raw_data),
            )

        return await self.call_action(
            envelope,
            action_data=action_data,
            target_data={ATTR_ENTITY_ID: targets},
        )
