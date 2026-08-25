"""Matrix transport for SuperNotify.

Sends messages to Matrix rooms using Home Assistant's `matrix` integration,
calling the native `matrix.send_message` service (not the thin legacy notify
wrapper), for granular control over format, images and threads.

Supported data keys (all optional):
    matrix_format           str     "text" | "html" (default: "html" when a
                                    title is present, otherwise "text")
    matrix_thread_id        str     Send the message into a Matrix thread
    matrix_attach_image     bool    Attach camera snapshot (default: False)
    matrix_priority_prefix  bool    Prefix message with an emoji derived from
                                    the SuperNotify priority (default: False):
                                    critical=siren, high=warning,
                                    low/minimum=small diamond, medium=none

Notes on the HA `matrix.send_message` service schema:
- The `data` sub-dict is STRICT (no ALLOW_EXTRA): only `format`, `images`
  and `thread_id` are accepted, any other key makes the whole call fail
  with `vol.Invalid`. Residual generic data keys are therefore NOT merged
  into the payload (they are dropped with a debug log), unlike the standard
  transport pattern.
- `target` is required and every entry must match the room regex
  `^[!|#][^:]*:.*` (room ID `!abc:server` or alias `#name:server`). A single
  invalid entry rejects the whole call, so targets are pre-filtered here and
  invalid ones are dropped with a debug log. Prefer room IDs, or aliases
  listed in the `rooms:` config of the matrix integration.
- There is no `title` field: the title is composed into the message body
  (bold + line break for html, plain line break for text).
- With `format: html` the core sets both `formatted_body` and plain `body`
  to the same string (no markup strip), so clients without HTML support
  will show raw tags. This mirrors core behaviour and is accepted.
- `images` is a list of LOCAL paths and the core checks
  `hass.config.is_allowed_path()`: the SuperNotify media path must be listed
  in `homeassistant.allowlist_external_dirs`, otherwise the image is dropped
  by the integration (the text message is still sent first).
- Matrix has no native message priority: the only priority mapping offered
  is the opt-in emoji prefix above.
"""

from __future__ import annotations

import html
import logging
import re
from typing import TYPE_CHECKING, Any

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import ATTR_DATA, TRANSPORT_MATRIX
from custom_components.supernotify.model import DebugTrace, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

# Slightly stricter subset of the core service regex `^[!|#][^:]*:.*`:
# require a room ID (!) or alias (#) sigil and a non-empty server part.
_MATRIX_ROOM_RE = re.compile(r"^[!#][^:]*:.+")

_VALID_FORMATS = ("text", "html")

# Opt-in emoji prefix per SuperNotify priority (medium: no prefix)
_PRIORITY_PREFIX = {
    "critical": "\U0001f6a8 ",  # police car light
    "high": "⚠️ ",  # warning sign
    "low": "\U0001f539 ",  # small blue diamond
    "minimum": "\U0001f539 ",  # small blue diamond
}


class MatrixTransport(Transport):
    """Notify via Matrix rooms using Home Assistant matrix integration."""

    name = TRANSPORT_MATRIX

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE | TransportFeature.IMAGES | TransportFeature.SNAPSHOT_IMAGE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "matrix.send_message"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        return config

    def validate_action(self, action: str | None) -> bool:
        """Validate that action is the matrix send_message service."""
        return action == "matrix.send_message"

    def select_rooms(self, envelope: Envelope) -> list[str]:
        """Filter envelope targets down to valid Matrix room IDs or aliases.

        The service rejects the whole call if any target fails the room
        regex, so invalid entries are dropped here (with a debug log) instead
        of being forwarded. Duplicates are removed preserving order.
        """
        raw_targets: list[str] = envelope.target.resolved_targets() if envelope.target else []
        rooms: list[str] = []
        for target in raw_targets:
            if isinstance(target, str) and _MATRIX_ROOM_RE.match(target):
                if target not in rooms:
                    rooms.append(target)
            else:
                _LOGGER.debug("SUPERNOTIFY matrix: skipping invalid room target %r", target)
        return rooms

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY matrix %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # Pop Matrix-specific data keys
        format_override = raw_data.pop("matrix_format", None)
        thread_id = raw_data.pop("matrix_thread_id", None)
        attach_image = boolify(raw_data.pop("matrix_attach_image", False), default=False)
        priority_prefix = boolify(raw_data.pop("matrix_priority_prefix", False), default=False)

        # Resolve and pre-validate room targets
        rooms = self.select_rooms(envelope)
        if not rooms:
            _LOGGER.warning("SUPERNOTIFY matrix: no valid room targets (expected !room:server or #alias:server)")
            self.record_error("no valid Matrix room targets", "deliver")
            return False

        # Resolve format: explicit override, or html when a title must be
        # composed in bold, plain text otherwise
        default_format = "html" if envelope.title else "text"
        if format_override:
            fmt = str(format_override).lower()
            if fmt not in _VALID_FORMATS:
                _LOGGER.warning("SUPERNOTIFY matrix: invalid matrix_format '%s', using '%s'", format_override, default_format)
                fmt = default_format
        else:
            fmt = default_format

        # Compose title into the message body (the service has no title field).
        # Only the title is escaped in html mode: the body may already contain
        # HTML the user wrote intentionally (consistent with core behaviour).
        message_text = envelope.message or ""
        if envelope.title:
            if fmt == "html":
                message_text = f"<b>{html.escape(envelope.title)}</b><br>{message_text}"
            else:
                message_text = f"{envelope.title}\n{message_text}"

        # Opt-in emoji prefix mapped from SuperNotify priority
        if priority_prefix:
            message_text = _PRIORITY_PREFIX.get(envelope.priority or "medium", "") + message_text

        # Grab camera snapshot if requested; images are local paths and the
        # matrix integration checks them against allowlist_external_dirs
        images: list[str] = []
        if attach_image:
            image_path = None
            try:
                image_path = await envelope.grab_image()
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY matrix: failed to grab image: %s", e)
            if image_path:
                images.append(str(image_path))
            else:
                _LOGGER.debug("SUPERNOTIFY matrix: no image available, sending text only")

        # Build the payload. The service data sub-dict is whitelist-only
        # (format / images / thread_id): residual generic data keys are NOT
        # merged, they would fail the whole call as extra keys.
        action_data: dict[str, Any] = {
            "message": message_text,
            "target": rooms,
        }
        service_data: dict[str, Any] = {"format": fmt}
        if thread_id:
            service_data["thread_id"] = str(thread_id)
        if images:
            service_data["images"] = images
        action_data[ATTR_DATA] = service_data

        if raw_data:
            _LOGGER.debug(
                "SUPERNOTIFY matrix: dropping data keys not supported by the strict service schema: %s",
                sorted(raw_data),
            )

        return await self.call_action(envelope, action_data=action_data)
