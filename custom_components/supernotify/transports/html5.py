"""HTML5 browser push transport for SuperNotify.

Sends web push notifications to browsers registered with Home Assistant's
`html5` integration, calling the modern `html5.send_message` entity service
(one `notify.*` entity per registered browser). The legacy `notify.html5`
platform is intentionally NOT used: its `ttl` and `priority` parameters are
read from send_message kwargs that the notify service never populates, so
urgency would silently always be "normal".

Supported data keys (all optional):
    html5_urgency              str        override web push urgency, one of
                                          low | normal | high. Default is
                                          mapped from the SuperNotify
                                          priority: critical/high -> high,
                                          medium -> normal,
                                          low/minimum -> low
    html5_tag                  str        notification tag: notifications
                                          sharing a tag replace each other
    html5_actions              list[dict] action buttons, each
                                          {action, title, icon}. Clicks fire
                                          `html5_notification.clicked`
                                          events with the `action` value
    html5_attach_image         bool       attach camera snapshot as `image`
                                          URL (default: False). Uses the
                                          shared media pipeline; the URL must
                                          be reachable by the browser, so an
                                          HTTPS external_url (or HA Cloud)
                                          is usually required
    html5_icon                 str        icon URL
    html5_badge                str        badge URL (Android status bar)
    html5_url                  str        URL opened when the notification
                                          is clicked (sent as `data.url`)
    html5_require_interaction  bool       keep the notification on screen
                                          until the user interacts with it
    html5_renotify             bool       alert again when a new notification
                                          replaces an existing tag
    html5_silent               bool       suppress sound/vibration. Mutually
                                          exclusive with html5_vibrate in the
                                          service schema (vol.Exclusive): when
                                          both are supplied, a truthy silent
                                          wins and vibrate is dropped, a falsy
                                          silent is dropped in favour of
                                          vibrate (warning either way)
    html5_vibrate              list[int]  vibration pattern in milliseconds,
                                          e.g. [200, 100, 200]. See
                                          html5_silent for the exclusivity
                                          rule
    html5_ttl                  int/dict   time-to-live: seconds or an HA
                                          duration dict, forwarded as-is
    html5_data                 dict       extra keys merged into the custom
                                          `data` field of the service call
                                          (html5_url wins on `url` clashes)

Notes on the HA `html5.send_message` service schema:
- The schema is a strict whitelist of first-class fields: unknown keys at
  the top level fail the whole call. Residual generic data keys are
  therefore NOT merged into the payload (dropped with a debug log); the
  `data` custom field, fed by `html5_url` / `html5_data`, is the explicit
  passthrough for anything else.
- `title` is REQUIRED by the schema; when the envelope has no title the
  HA default "Home Assistant" is used.
- Targets are `notify.*` entities created by browser push registrations
  (html5 config entry with VAPID keys). Non-matching targets are dropped
  with a debug log; no valid target fails the delivery.
- Expired push subscriptions (410 GONE) are handled by the core, which
  unregisters the browser and raises: call_action then returns False.

Internal data keys filtered upstream by notification.py and NOT popped
here: force_resend, spoken_message.

References:
- HTML5 push integration: https://www.home-assistant.io/integrations/html5/

"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify.common import boolify
from custom_components.supernotify.const import (
    ATTR_DATA,
    ATTR_MEDIA_SNAPSHOT_URL,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_SELECT,
    TRANSPORT_HTML5,  # added via const_additions_html5.py
)
from custom_components.supernotify.model import DebugTrace, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope

_LOGGER = logging.getLogger(__name__)

RE_VALID_HTML5 = r"notify\.[A-Za-z0-9_]+"
_HTML5_TARGET_RE = re.compile(r"^notify\.[A-Za-z0-9_]+$")

# HA schema default for the required title field
_DEFAULT_TITLE = "Home Assistant"

_VALID_URGENCY = ("low", "normal", "high")

# SuperNotify priority -> web push urgency
_URGENCY_BY_PRIORITY = {
    "critical": "high",
    "high": "high",
    "medium": "normal",
    "low": "low",
    "minimum": "low",
}


class HTML5Transport(Transport):
    """Notify browsers via the Home Assistant html5 web push integration."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    name = TRANSPORT_HTML5

    @property
    def supported_features(self) -> TransportFeature:
        return (
            TransportFeature.MESSAGE
            | TransportFeature.TITLE
            | TransportFeature.IMAGES
            | TransportFeature.SNAPSHOT_IMAGE
            | TransportFeature.ACTIONS
        )

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.action = "html5.send_message"
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        config.delivery_defaults.options = {
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
            OPTION_TARGET_SELECT: [RE_VALID_HTML5],
        }
        return config

    def validate_action(self, action: str | None) -> bool:
        """Validate that action is the html5 send_message service."""
        return action == "html5.send_message"

    def select_targets(self, envelope: Envelope) -> list[str]:
        """Filter envelope targets down to html5 `notify.*` entity ids.

        The service is entity-based: every target must be a notify entity
        created by a browser push registration. Non-matching entries are
        dropped with a debug log; duplicates are removed preserving order.
        """
        raw_targets: list[str] = envelope.target.resolved_targets() if envelope.target else []
        targets: list[str] = []
        for target in raw_targets:
            if isinstance(target, str) and _HTML5_TARGET_RE.match(target):
                if target not in targets:
                    targets.append(target)
            else:
                _LOGGER.debug("SUPERNOTIFY html5: skipping invalid target %r (expected notify.*)", target)
        return targets

    async def _resolve_image_url(self, envelope: Envelope) -> str | None:
        """Resolve a browser-reachable snapshot URL.

        Order of resolution:
          1. snapshot URL already in envelope media, absolutised
          2. envelope.grab_image() + media_storage.object_url() (shared
             media pipeline; never a local path)
          3. None
        """
        snapshot_url = envelope.media.get(ATTR_MEDIA_SNAPSHOT_URL) if envelope.media else None
        if snapshot_url:
            return self.hass_api.abs_url(snapshot_url)

        image_path = None
        try:
            image_path = await envelope.grab_image()
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY html5: failed to grab image: %s", e)
        if image_path:
            try:
                return await self.context.media_storage.object_url(image_path)
            except Exception as e:
                _LOGGER.debug("SUPERNOTIFY html5: object_url failed for %s: %s", image_path, e)
        return None

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        _LOGGER.debug("SUPERNOTIFY html5 %s", envelope.message)

        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}

        # Pop html5-specific data keys
        urgency_override = raw_data.pop("html5_urgency", None)
        tag = raw_data.pop("html5_tag", None)
        actions = raw_data.pop("html5_actions", None)
        attach_image = boolify(raw_data.pop("html5_attach_image", False), default=False)
        icon = raw_data.pop("html5_icon", None)
        badge = raw_data.pop("html5_badge", None)
        click_url = raw_data.pop("html5_url", None)
        require_interaction_raw = raw_data.pop("html5_require_interaction", None)
        renotify_raw = raw_data.pop("html5_renotify", None)
        silent_raw = raw_data.pop("html5_silent", None)
        vibrate = raw_data.pop("html5_vibrate", None)
        ttl = raw_data.pop("html5_ttl", None)
        custom_data = raw_data.pop("html5_data", None)

        # Resolve and pre-validate notify entity targets
        targets = self.select_targets(envelope)
        if not targets:
            _LOGGER.warning("SUPERNOTIFY html5: no valid targets (expected notify.* entities)")
            self.record_error("no valid html5 notify entity targets", "deliver")
            return False

        # Resolve urgency: explicit valid override, else mapped from priority
        urgency = _URGENCY_BY_PRIORITY.get(envelope.priority or "medium", "normal")
        if urgency_override is not None:
            candidate = str(urgency_override).lower()
            if candidate in _VALID_URGENCY:
                urgency = candidate
            else:
                _LOGGER.warning(
                    "SUPERNOTIFY html5: invalid html5_urgency %r (valid: %s), using '%s'",
                    urgency_override,
                    _VALID_URGENCY,
                    urgency,
                )

        # The service schema declares silent and vibrate as mutually
        # exclusive (vol.Exclusive shares the "silent_xor_vibrate" group):
        # sending both keys fails the whole call, whatever their values
        if silent_raw is not None and vibrate is not None:
            if boolify(silent_raw, default=False):
                _LOGGER.warning("SUPERNOTIFY html5: html5_silent and html5_vibrate are mutually exclusive, dropping vibrate")
                vibrate = None
            else:
                _LOGGER.warning(
                    "SUPERNOTIFY html5: html5_silent and html5_vibrate are mutually exclusive, dropping falsy silent"
                )
                silent_raw = None

        # Build the payload: title is REQUIRED by the service schema
        action_data: dict[str, Any] = {
            "title": envelope.title or _DEFAULT_TITLE,
            "message": envelope.message or "",
            "urgency": urgency,
        }
        if icon:
            action_data["icon"] = str(icon)
        if badge:
            action_data["badge"] = str(badge)
        if tag:
            action_data["tag"] = str(tag)
        if actions is not None:
            if isinstance(actions, list):
                action_data["actions"] = actions
            else:
                _LOGGER.warning("SUPERNOTIFY html5: html5_actions must be a list of dicts, dropping %r", actions)
        if renotify_raw is not None:
            action_data["renotify"] = boolify(renotify_raw, default=False)
        if silent_raw is not None:
            action_data["silent"] = boolify(silent_raw, default=False)
        if require_interaction_raw is not None:
            action_data["require_interaction"] = boolify(require_interaction_raw, default=False)
        if vibrate is not None:
            if isinstance(vibrate, list):
                action_data["vibrate"] = vibrate
            else:
                _LOGGER.warning("SUPERNOTIFY html5: html5_vibrate must be a list of ints, dropping %r", vibrate)
        if ttl is not None:
            action_data["ttl"] = ttl

        # Attach camera snapshot as browser-reachable URL (never a local path)
        if attach_image:
            image_url = await self._resolve_image_url(envelope)
            if image_url:
                action_data["image"] = str(image_url)
            else:
                _LOGGER.debug("SUPERNOTIFY html5: no image URL available, sending without image")

        # Custom `data` field: the only passthrough the strict schema allows.
        # html5_data is merged first so the explicit html5_url wins on `url`.
        data_field: dict[str, Any] = {}
        if isinstance(custom_data, dict):
            data_field.update(custom_data)
        elif custom_data is not None:
            _LOGGER.warning("SUPERNOTIFY html5: html5_data must be a dict, dropping %r", custom_data)
        if click_url:
            data_field["url"] = str(click_url)
        if data_field:
            action_data[ATTR_DATA] = data_field

        # Residual generic keys are NOT merged: the service schema is a
        # strict whitelist and any extra top-level key fails the whole call.
        if raw_data:
            _LOGGER.debug(
                "SUPERNOTIFY html5: dropping data keys not supported by the strict service schema: %s",
                sorted(raw_data),
            )

        target_data = {ATTR_ENTITY_ID: targets}
        return await self.call_action(envelope, action_data=action_data, target_data=target_data)
