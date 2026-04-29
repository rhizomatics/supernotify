"""Telegram transport for SuperNotify.

Sends push notifications via Telegram using Home Assistant's telegram_bot integration.
Supports text messages, photos (with optional captions), and inline action buttons.
Uses telegram_bot service for granular control over formatting, media types, and protection.

Supported data keys (all optional):
    telegram_parse_mode         str         "HTML" | "Markdown" (default: None, plain text)
    telegram_disable_notification bool      Override silent mode (overrides priority mapping)
    telegram_protect_content    bool       Block forward/save (default: False)
    telegram_chat_id            str|int    Override target chat_id (default: None)
    telegram_reply_to_message_id int       Reply to message ID (default: None)
    telegram_inline_keyboard    list       Custom action buttons in [[{text, callback_data}]] format
    telegram_attach_image       bool       Attach camera snapshot (default: False)
    telegram_image_as_document  bool       Send image as document without compression (default: False)

Notes on the HA telegram_bot service schema:
- `parse_mode` accepts only lowercase values: 'html', 'markdown',
  'markdownv2', 'plain_text'. We normalise the user-provided value to
  lowercase before forwarding.
- `protect_content` is a Telegram Bot API parameter but the HA
  `telegram_bot` integration does not currently expose it as a service-data
  key (voluptuous rejects it as `extra keys not allowed`). We accept the
  data key for forward-compatibility but do NOT forward it to the service.
- `inline_keyboard` for HA is a list of rows where each row is a list of
  `[label, callback_or_url]` 2-element lists (NOT dicts with
  `text`/`callback_data` keys). Example: `[[["OK","/ok"],["Cancel","/cancel"]]]`.
"""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING, Any

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import TRANSPORT_TELEGRAM
from custom_components.supernotify.model import DebugTrace, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

_PRIORITY_MAP = {
    "critical": False,  # notify (sound + vibration)
    "high": False,  # notify (sound)
    "medium": False,  # notify (sound)
    "low": True,  # silent
    "minimum": True,  # silent
}

# Telegram Bot API limits
_MAX_MESSAGE_LENGTH = 4096
_MAX_CAPTION_LENGTH = 1024


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return html.escape(text) if text else ""


def _normalise_inline_keyboard(keyboard: list) -> list:
    """Normalise a user-supplied inline keyboard to the HA telegram_bot shape.

    Accepts:
    - HA-native: list of rows where each row is a list of `[label, callback]`
      2-element lists. Returned unchanged.
    - Telegram Bot API native: list of rows where each row is a list of
      `{"text": label, "callback_data": callback}` dicts. Converted to the
      HA shape.
    - Mixed rows are tolerated (each button is normalised independently).

    Returns the keyboard in the HA shape, or `[]` if the input is malformed.
    """
    if not isinstance(keyboard, list):
        return []
    out: list = []
    for row in keyboard:
        if not isinstance(row, list):
            continue
        out_row: list = []
        for btn in row:
            if isinstance(btn, list) and len(btn) >= 2:
                # Already in HA shape: [label, callback_or_url]
                out_row.append([str(btn[0]), str(btn[1])])
            elif isinstance(btn, dict):
                label = btn.get("text") or btn.get("title") or btn.get("label")
                callback = btn.get("callback_data") or btn.get("action") or btn.get("url")
                if label and callback:
                    out_row.append([str(label), str(callback)])
        if out_row:
            out.append(out_row)
    return out


def _build_inline_keyboard(actions: list) -> list:
    """Convert SuperNotify actions to HA telegram_bot inline keyboard format.

    SuperNotify actions are dicts with keys "title" (button label)
    and "action" (callback identifier). The HA telegram_bot service expects
    a list of rows where each row is a list of [label, callback_or_url]
    2-element lists (NOT dicts with text/callback_data keys).
    Example shape: [[["OK", "/ack_ok"], ["Open HA", "/open"]]]

    Limits to max 5 buttons (single row) and 64-byte callback_data.
    """
    if not actions or not isinstance(actions, list):
        return []

    row = []
    for i, action in enumerate(actions):
        if i >= 5:
            _LOGGER.warning("SUPERNOTIFY telegram: more than 5 actions, truncating to 5")
            break

        if not isinstance(action, dict):
            _LOGGER.warning("SUPERNOTIFY telegram: action not a dict, skipped")
            continue

        # SuperNotify action keys: "title" for label, "action" for callback id.
        # Also tolerate Telegram-native "text"/"callback_data" for users who
        # craft the action list manually.
        label = action.get("title") or action.get("text") or action.get("label")
        callback = action.get("action") or action.get("callback_data") or action.get("id")

        if not label or not callback:
            _LOGGER.warning("SUPERNOTIFY telegram: action missing 'title' or 'action' key, skipped")
            continue

        # Truncate callback_data to 64 bytes UTF-8 per Telegram API
        callback_str = str(callback)
        encoded = callback_str.encode("utf-8")
        if len(encoded) > 64:
            callback_str = encoded[:64].decode("utf-8", errors="ignore")
            _LOGGER.warning("SUPERNOTIFY telegram: callback_data truncated to 64 bytes: %s", callback_str)

        # HA format: [label, callback_or_url] 2-element list
        row.append([str(label), callback_str])

    return [row] if row else []


class TelegramTransport(Transport):
    """Notify via Telegram using Home Assistant telegram_bot integration."""

    name = TRANSPORT_TELEGRAM

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
        config.delivery_defaults.action = "telegram_bot.send_message"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        return config

    def validate_action(self, action: str | None) -> bool:
        """Validate that action is one of the supported telegram_bot services."""
        if not action:
            return False
        return action in (
            "telegram_bot.send_message",
            "telegram_bot.send_photo",
            "telegram_bot.send_document",
        )

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY telegram %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # Pop Telegram-specific data keys
        parse_mode = raw_data.pop("telegram_parse_mode", None)
        disable_notification_override = raw_data.pop("telegram_disable_notification", None)
        # `telegram_protect_content` is accepted but currently NOT forwarded
        # because the HA telegram_bot service schema rejects it. Pop to keep
        # it out of the residual raw_data merge below.
        raw_data.pop("telegram_protect_content", None)
        chat_id_override = raw_data.pop("telegram_chat_id", None)
        reply_to_message_id = raw_data.pop("telegram_reply_to_message_id", None)
        custom_keyboard = raw_data.pop("telegram_inline_keyboard", None)
        attach_image = boolify(raw_data.pop("telegram_attach_image", False), default=False)
        image_as_document = boolify(raw_data.pop("telegram_image_as_document", False), default=False)

        # Resolve target chat_id.
        # `envelope.delivery.target` is a SuperNotify `Target` object with a
        # `.targets` attribute (dict[category, list[id]]), where category is
        # ATTR_PHONE, ATTR_EMAIL, ATTR_MOBILE_APP_ID, etc. For Telegram we
        # prefer `phone` (Telegram chat IDs are stored there by convention).
        # Also accept legacy raw shapes: dict, list, or scalar string/int.
        raw_target: Any = chat_id_override
        if not raw_target and envelope.delivery:
            raw_target = envelope.delivery.target

        # Target object: extract first id from preferred categories
        if hasattr(raw_target, "targets") and isinstance(raw_target.targets, dict):
            categorised = raw_target.targets
            # Prefer phone (Telegram convention), then any non-empty list
            preferred = ("phone", "chat_id")
            picked = None
            for cat in preferred:
                if categorised.get(cat):
                    picked = categorised[cat][0]
                    break
            if not picked:
                for v in categorised.values():
                    if isinstance(v, list) and v:
                        picked = v[0]
                        break
            raw_target = picked

        # Legacy dict shape (pre-Target object): pick first list value
        if isinstance(raw_target, dict):
            for v in raw_target.values():
                if isinstance(v, list) and v:
                    raw_target = v[0]
                    break
                if v:
                    raw_target = v
                    break
        elif isinstance(raw_target, list) and raw_target:
            raw_target = raw_target[0]

        if not raw_target:
            _LOGGER.warning("SUPERNOTIFY telegram: chat_id not configured in delivery data")
            self.record_error("chat_id not configured", "deliver")
            return False

        # telegram_bot service expects int (or list of int). Group chat IDs are
        # negative integers; channel usernames (@channel) would be string but
        # are not currently supported by this transport.
        try:
            chat_id: int = int(raw_target)
        except (TypeError, ValueError):
            _LOGGER.warning("SUPERNOTIFY telegram: chat_id %r is not numeric (expected int)", raw_target)
            self.record_error(f"chat_id {raw_target!r} not numeric", "deliver")
            return False

        # Validate and normalise parse_mode. The HA telegram_bot service
        # schema accepts only lowercase values: html / markdown / markdownv2
        # / plain_text. We accept the camel-cased aliases the user may type
        # (HTML, Markdown, MarkdownV2) and normalise.
        # If the user does NOT specify a parse_mode, we default to plain_text
        # rather than relying on the telegram_bot service default (markdown),
        # because plain text bodies often contain `_` or `*` characters
        # (e.g. "protect_content") that markdown would interpret as opening
        # italic/bold and trigger "Can't parse entities" errors at Telegram.
        if parse_mode:
            normalised = str(parse_mode).lower()
            if normalised not in ("html", "markdown", "markdownv2", "plain_text"):
                _LOGGER.warning("SUPERNOTIFY telegram: invalid parse_mode '%s', ignoring", parse_mode)
                parse_mode = "plain_text"
            else:
                parse_mode = normalised
        else:
            parse_mode = "plain_text"

        # Map priority to disable_notification boolean
        if disable_notification_override is not None:
            disable_notification = boolify(disable_notification_override, default=False)
        else:
            disable_notification = _PRIORITY_MAP.get(envelope.priority or "medium", False)

        # Build message text with title if present
        message_text = envelope.message or ""
        if envelope.title:
            if parse_mode == "html":
                # The body may already contain HTML the user wrote intentionally
                # (e.g. <b>...</b>). Only escape the title (which is typically
                # plain text) and prepend it bolded.
                message_text = f"<b>{_escape_html(envelope.title)}</b>\n\n{message_text}"
            elif parse_mode in ("markdown", "markdownv2"):
                message_text = f"*{envelope.title}*\n\n{message_text}"
            else:
                message_text = f"{envelope.title}\n\n{message_text}"

        # Truncate message to Telegram limit
        if len(message_text) > _MAX_MESSAGE_LENGTH:
            message_text = message_text[:_MAX_MESSAGE_LENGTH]
            _LOGGER.debug("SUPERNOTIFY telegram: message truncated to %d chars", _MAX_MESSAGE_LENGTH)

        # Convert actions to inline keyboard. The HA telegram_bot service
        # expects rows of [label, callback_or_url] 2-element lists. If the
        # user passes a Telegram Bot API native dict shape
        # ([[{text, callback_data}, ...], ...]), normalise it on the fly.
        inline_keyboard = None
        if custom_keyboard:
            inline_keyboard = _normalise_inline_keyboard(custom_keyboard)
        elif envelope.actions:
            inline_keyboard = _build_inline_keyboard(envelope.actions)

        # Build base action data. The HA telegram_bot service schema uses
        # `target` (list of int chat IDs) as the primary recipient field; we
        # pass a single-element list for one chat. send_message/send_photo/
        # send_document all accept the same `target` key.
        action_data: dict[str, Any] = {"target": [chat_id]}

        # Determine if we have an image to attach
        image_path = None
        if attach_image:
            try:
                image_path = await envelope.grab_image()
                _LOGGER.debug("SUPERNOTIFY telegram: image grabbed at %s", image_path)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY telegram: failed to grab image: %s", e)
                image_path = None

        # Select service and build service-specific payload
        service_action = "telegram_bot.send_message"

        if image_path and image_as_document:
            # Send image as document (no compression). The telegram_bot HA
            # service schema uses `file` for both send_photo and send_document
            # (local path or http(s) URL).
            service_action = "telegram_bot.send_document"
            action_data["file"] = str(image_path)
            if message_text:
                action_data["caption"] = message_text[:_MAX_CAPTION_LENGTH]
                if parse_mode:
                    action_data["parse_mode"] = parse_mode
        elif image_path:
            # Send image as photo with caption (`file` is the schema field
            # name; the telegram_bot service infers content-type).
            service_action = "telegram_bot.send_photo"
            action_data["file"] = str(image_path)
            if message_text:
                action_data["caption"] = message_text[:_MAX_CAPTION_LENGTH]
                if parse_mode:
                    action_data["parse_mode"] = parse_mode
        else:
            # Send text message
            action_data["message"] = message_text
            if parse_mode:
                action_data["parse_mode"] = parse_mode

        # Add optional parameters
        if disable_notification:
            action_data["disable_notification"] = True

        # protect_content is intentionally NOT forwarded - the HA
        # telegram_bot service schema does not accept this key (voluptuous
        # rejects it as `extra keys not allowed`). Kept as a documented data
        # key for forward-compatibility once HA exposes it.

        if reply_to_message_id:
            action_data["reply_to_message_id"] = reply_to_message_id

        if inline_keyboard:
            action_data["inline_keyboard"] = inline_keyboard

        # Merge remaining generic data keys
        action_data.update(raw_data)

        # Use the base-class call_action() to invoke the dynamically chosen
        # telegram_bot service (send_message / send_photo / send_document).
        # call_action() handles call-record tracking, error capture, and the
        # envelope.delivered/calls bookkeeping that SuperNotify uses to
        # decide success vs. fallback. `implied_target=True` tells SuperNotify
        # the target is implied by the in-payload chat_id (so the
        # `TargetRequired.ALWAYS` check does not skip the delivery).
        return await self.call_action(
            envelope,
            qualified_action=service_action,
            action_data=action_data,
            implied_target=True,
        )
