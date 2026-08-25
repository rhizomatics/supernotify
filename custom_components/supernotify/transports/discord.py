"""Discord transport for SuperNotify.

Sends messages to Discord channels or users via Home Assistant's `discord`
integration (legacy notify platform). The service is typically
`notify.discord`, but the actual slug depends on the config entry name
(e.g. `notify.discord_2`), so any `notify.*` action is accepted.

Supported data keys (all optional):
    discord_embed            dict   Discord embed passthrough, forwarded as
                                    service `data.embed` (title, description,
                                    color, url, fields, footer, author,
                                    thumbnail, image — HA core schema).
                                    `color` must be an integer (e.g. 0xFF0000
                                    in YAML == 16711680); hex strings are
                                    passed through unchanged and may be
                                    rejected downstream by nextcord.
    discord_attach_image     bool   Attach camera snapshot as a local file
                                    path in `data.images` (default: False)
    discord_image_urls       list   Image URLs forwarded as `data.urls`
                                    (a single string is wrapped into a list)
    discord_verify_ssl       bool   SSL verification for `data.urls`
                                    downloads (service default: True; only
                                    forwarded when explicitly set)
    discord_priority_prefix  bool   Prefix message with an emoji derived from
                                    the SuperNotify priority (default: False):
                                    critical=siren, high=warning,
                                    low/minimum=small diamond, medium=none

Notes on the HA `discord` notify service:
- `target` is REQUIRED: a list of numeric Discord channel or user IDs
  (snowflakes, strings of digits). Without a target the service logs an
  error and sends nothing, so targets are pre-filtered here: non-numeric
  entries are dropped with a debug log and an empty result fails the
  delivery (TargetRequired.ALWAYS, no sensible default exists).
- There is no `title` field in the service schema: the title is composed
  into the message body as Discord markdown (`**title**` + newline +
  message) — but ONLY when `discord_embed` does not carry its own `title`
  (the embed already renders a title in that case, so the body stays plain).
- `data.images` is a list of LOCAL paths checked by the integration with
  `hass.config.is_allowed_path()`: the SuperNotify media path must be listed
  in `homeassistant.allowlist_external_dirs` in configuration.yaml,
  otherwise the attachment is dropped by the integration.
- `data.urls` entries are checked with `hass.config.is_allowed_external_url()`:
  every URL must be covered by `homeassistant.allowlist_external_urls` in
  configuration.yaml. The integration downloads at most 8MB per attachment.
- The service `data` dict is permissive and unknown keys are silently
  ignored downstream: for cleanliness residual generic data keys are NOT
  forwarded (dropped with a debug log), consistent with the Matrix transport.
- Discord has no native message priority: the only mapping offered is the
  opt-in emoji prefix above.
- Message content is truncated to the Discord limit of 2000 characters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import ATTR_DATA, TRANSPORT_DISCORD
from custom_components.supernotify.model import DebugTrace, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

# Discord message content hard limit
_MAX_MESSAGE_LENGTH = 2000

# Opt-in emoji prefix per SuperNotify priority (medium: no prefix)
_PRIORITY_PREFIX = {
    "critical": "\U0001f6a8 ",  # police car light
    "high": "⚠️ ",  # warning sign
    "low": "\U0001f539 ",  # small blue diamond
    "minimum": "\U0001f539 ",  # small blue diamond
}


class DiscordTransport(Transport):
    """Notify via Discord channels or users using Home Assistant discord integration."""

    name = TRANSPORT_DISCORD

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE | TransportFeature.IMAGES | TransportFeature.SNAPSHOT_IMAGE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "notify.discord"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        return config

    def validate_action(self, action: str | None) -> bool:
        """Validate that action is a notify.* service.

        The discord integration registers a legacy notify service whose slug
        depends on the config entry name (notify.discord, notify.discord_2,
        ...), so any non-empty notify domain action is accepted.
        """
        if action and action.startswith("notify.") and action.split(".", 1)[1]:
            return True
        _LOGGER.warning(
            "SUPERNOTIFY discord: action must be a notify.* service (e.g. notify.discord), got: %r",
            action,
        )
        return False

    def select_channels(self, envelope: Envelope) -> list[str]:
        """Filter envelope targets down to numeric Discord channel/user IDs.

        Discord IDs are snowflakes (positive integers, passed as strings of
        digits). The service handles an invalid ID with a warning and moves
        on, but targets are cleaned here anyway: non-numeric entries are
        dropped with a debug log. Duplicates are removed preserving order.
        """
        raw_targets: list[Any] = envelope.target.resolved_targets() if envelope.target else []
        channels: list[str] = []
        for target in raw_targets:
            candidate = str(target).strip() if target is not None else ""
            try:
                numeric_id = int(candidate)
            except ValueError:
                numeric_id = -1
            if numeric_id <= 0:
                _LOGGER.debug("SUPERNOTIFY discord: skipping non-numeric channel target %r", target)
                continue
            if candidate not in channels:
                channels.append(candidate)
        return channels

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        _LOGGER.debug("SUPERNOTIFY discord %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # Pop Discord-specific data keys
        embed = raw_data.pop("discord_embed", None)
        attach_image = boolify(raw_data.pop("discord_attach_image", False), default=False)
        image_urls = raw_data.pop("discord_image_urls", None)
        verify_ssl_raw = raw_data.pop("discord_verify_ssl", None)
        priority_prefix = boolify(raw_data.pop("discord_priority_prefix", False), default=False)

        # Resolve and pre-validate numeric channel/user ID targets
        channels = self.select_channels(envelope)
        if not channels:
            _LOGGER.warning("SUPERNOTIFY discord: no valid targets (expected numeric channel or user IDs)")
            self.record_error("no valid Discord channel or user ID targets", "deliver")
            return False

        # Validate embed passthrough shape
        if embed is not None and not isinstance(embed, dict):
            _LOGGER.warning("SUPERNOTIFY discord: discord_embed must be a dict, ignoring %r", embed)
            embed = None

        # Compose title into the message body as Discord markdown (the
        # service has no title field), unless the embed carries its own
        # title (the embed then renders the title and the body stays plain).
        embed_has_title = bool(embed and embed.get("title"))
        message_text = envelope.message or ""
        if envelope.title and not embed_has_title:
            message_text = f"**{envelope.title}**\n{message_text}"

        # Opt-in emoji prefix mapped from SuperNotify priority
        if priority_prefix:
            message_text = _PRIORITY_PREFIX.get(envelope.priority or "medium", "") + message_text

        # Truncate to the Discord content limit
        if len(message_text) > _MAX_MESSAGE_LENGTH:
            message_text = message_text[:_MAX_MESSAGE_LENGTH]
            _LOGGER.debug("SUPERNOTIFY discord: message truncated to %d chars", _MAX_MESSAGE_LENGTH)

        # Grab camera snapshot if requested; images are local paths and the
        # discord integration checks them against allowlist_external_dirs
        images: list[str] = []
        if attach_image:
            image_path = None
            try:
                image_path = await envelope.grab_image()
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY discord: failed to grab image: %s", e)
            if image_path:
                images.append(str(image_path))
            else:
                _LOGGER.debug("SUPERNOTIFY discord: no image available, sending text only")

        # Normalise image URLs (allowlist_external_urls applies downstream)
        urls: list[str] = []
        if image_urls is not None:
            if isinstance(image_urls, str):
                image_urls = [image_urls]
            if isinstance(image_urls, list):
                urls = [str(u) for u in image_urls if u]
            else:
                _LOGGER.warning("SUPERNOTIFY discord: discord_image_urls must be a list, ignoring %r", image_urls)

        # Build the payload. The service data dict is whitelist-only here
        # (embed / images / urls / verify_ssl): residual generic data keys
        # are NOT merged, the service would silently ignore them anyway.
        action_data: dict[str, Any] = {
            "message": message_text,
            "target": channels,
        }
        service_data: dict[str, Any] = {}
        if embed:
            service_data["embed"] = embed
        if images:
            service_data["images"] = images
        if urls:
            service_data["urls"] = urls
        if verify_ssl_raw is not None:
            service_data["verify_ssl"] = boolify(verify_ssl_raw, default=True)
        if service_data:
            action_data[ATTR_DATA] = service_data

        if raw_data:
            _LOGGER.debug(
                "SUPERNOTIFY discord: dropping data keys not supported by the service data whitelist: %s",
                sorted(raw_data),
            )

        return await self.call_action(envelope, action_data=action_data)
