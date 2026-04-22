"""Mobile App Companion transport for SuperNotify.

Sends push notifications to HA Companion App on iOS and Android devices.
Supports per-device delivery with automatic snooze on failure.

Priority mapping (auto, overridable via push_critical_level_ios):
    critical  → iOS: interruption_level=critical  + Android: ttl=0
    high      → iOS: interruption_level=time-sensitive
    medium    → iOS: interruption_level=active    (default)
    low       → iOS: interruption_level=passive
    minimum   → iOS: interruption_level=passive

New data keys (all optional):
    push_critical_level_ios     str   iOS interruption_level override
                                      ("passive","active","time-sensitive","critical")
                                      If omitted, auto-mapped from SuperNotify priority.
    push_critical_ttl           int   Android FCM TTL in ms (0=no caching/instant).
                                      Auto-set to 0 for critical priority if not set.
    push_critical_android_priority int  Android FCM priority override (1=min, 5=max).
    push_subtitle               str   iOS subtitle (line between title and message, iOS 10+)
    push_notification_tag       str   Notification tag for replacement (iOS) / grouping (Android)
    push_clear_notification     bool  Send clear_notification to dismiss previous same-tag notification.
                                      Requires push_notification_tag to be set.
    push_tts_text               str   Android TTS text read aloud on device (Android 8+).
                                      If omitted, push TTS is not activated.
    push_tts_locale             str   BCP-47 language for TTS (e.g. "it-IT", "en-US").
                                      Only used when push_tts_text is set.
    push_tts_engine             str   TTS engine package (e.g. "com.google.android.tts").
                                      Only used when push_tts_text is set.
    push_command_screen_on      bool  Android: turn on device screen on delivery (Android 8+)
    push_command_dnd            str   Android: change Do Not Disturb ("toggle","off","on")
    push_command_ringer_mode    str   Android: change ringer mode ("silent","vibrate","normal")
    push_channel_override       str   Android notification channel override (e.g. "alarm","general")
    push_alarm_stream           bool  Android: route audio through alarm stream (interrupts DND/silent)
    push_alarm_stream_max       bool  Android: alarm stream at maximum device volume

"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from aiohttp import ClientResponse, ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from homeassistant.components.notify.const import ATTR_DATA

import custom_components.supernotify.const as const
from custom_components.supernotify.const import (
    ATTR_ACTION_CATEGORY,
    ATTR_ACTION_URL,
    ATTR_ACTION_URL_TITLE,
    ATTR_DEFAULT,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_MOBILE_APP_ID,
    OPTION_DEVICE_DISCOVERY,
    OPTION_DEVICE_DOMAIN,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_MOBILE_PUSH,
)
from custom_components.supernotify.media_grab import grab_image
from custom_components.supernotify.model import (
    CommandType,
    DebugTrace,
    DeliveryConfig,
    MessageOnlyPolicy,
    QualifiedTargetType,
    RecipientType,
    Target,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)

# iOS interruption_level mapping from SuperNotify priority
IOS_INTERRUPTION_MAP: dict[str, str] = {
    const.PRIORITY_CRITICAL: "critical",
    const.PRIORITY_HIGH:     "time-sensitive",
    const.PRIORITY_MEDIUM:   "active",
    const.PRIORITY_LOW:      "passive",
    const.PRIORITY_MINIMUM:  "passive",
}

# Android FCM TTL auto-set for critical priority (0 = instant, no FCM caching)
ANDROID_CRITICAL_TTL = 0


class MobilePushTransport(Transport):
    name = TRANSPORT_MOBILE_PUSH

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.action_titles: dict[str, str] = {}
        self.action_title_failures: dict[str, float] = {}

    @property
    def supported_features(self) -> TransportFeature:
        return (
            TransportFeature.MESSAGE
            | TransportFeature.TITLE
            | TransportFeature.ACTIONS
            | TransportFeature.IMAGES
            | TransportFeature.VIDEO
            | TransportFeature.SNAPSHOT_IMAGE
        )

    def extra_attributes(self) -> dict[str, Any]:
        return {"action_titles": self.action_titles, "action_title_failures": self.action_title_failures}

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.target_required = TargetRequired.ALWAYS
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_TARGET_CATEGORIES: [ATTR_MOBILE_APP_ID],
            OPTION_DEVICE_DISCOVERY: False,
            OPTION_DEVICE_DOMAIN: ["mobile_app"],
        }
        return config

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:  # noqa: ARG002
        return self.delivery_defaults

    def validate_action(self, action: str | None) -> bool:
        return action is None

    def _extract_push_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract and remove SuperNotify-specific push_* keys from raw_data.

        Modifies raw_data in-place via pop().
        After this call, raw_data contains only passthrough keys for the Companion App.

        Returns a dict with all extracted push_* values (None if not provided).
        """
        return {
            # iOS
            "critical_level_ios":        raw_data.pop("push_critical_level_ios", None),
            "subtitle":                  raw_data.pop("push_subtitle", None),
            # Android critical
            "critical_ttl":              raw_data.pop("push_critical_ttl", None),
            "critical_android_priority": raw_data.pop("push_critical_android_priority", None),
            "channel_override":          raw_data.pop("push_channel_override", None),
            "alarm_stream":              raw_data.pop("push_alarm_stream", False),
            "alarm_stream_max":          raw_data.pop("push_alarm_stream_max", False),
            # Android TTS
            "tts_text":                  raw_data.pop("push_tts_text", None),
            "tts_locale":                raw_data.pop("push_tts_locale", None),
            "tts_engine":                raw_data.pop("push_tts_engine", None),
            # Android Notification Commands
            "command_screen_on":         raw_data.pop("push_command_screen_on", None),
            "command_dnd":               raw_data.pop("push_command_dnd", None),
            "command_ringer_mode":       raw_data.pop("push_command_ringer_mode", None),
            # Cross-platform
            "notification_tag":          raw_data.pop("push_notification_tag", None),
            "clear_notification":        raw_data.pop("push_clear_notification", False),
        }

    def _apply_android_payload(
        self,
        data: dict[str, Any],
        push_data: dict[str, Any],
        priority: str | None,
    ) -> None:
        """Apply Android-specific fields to the notification data dict.

        Android fields live flat in data{}, not inside the push{} sub-dict.
        """
        # Channel override (Android 8+, determines sound/vibration/LED)
        if push_data["channel_override"]:
            data["channel"] = push_data["channel_override"]

        # Alarm stream: routes audio through alarm stream, interrupts DND/silent
        if push_data["alarm_stream"]:
            data["alarm_stream"] = True
            if push_data["alarm_stream_max"]:
                data["alarm_stream_max"] = True

        # FCM TTL: auto-set to 0 for critical (instant delivery, no FCM caching)
        if push_data["critical_ttl"] is not None:
            data["ttl"] = push_data["critical_ttl"]
        elif priority == const.PRIORITY_CRITICAL:
            data["ttl"] = ANDROID_CRITICAL_TTL

        # FCM priority override
        if push_data["critical_android_priority"] is not None:
            data["priority"] = push_data["critical_android_priority"]

        # Android TTS: read message aloud on device (Android 8+)
        if push_data["tts_text"]:
            data["tts_text"] = push_data["tts_text"]
            if push_data["tts_locale"]:
                data["tts_text_language"] = push_data["tts_locale"]
            if push_data["tts_engine"]:
                data["tts_engine"] = push_data["tts_engine"]

        # Notification Commands (Android 8+)
        if push_data["command_screen_on"]:
            data["command_screen_on"] = True
        if push_data["command_dnd"]:
            data["command_dnd"] = push_data["command_dnd"]
        if push_data["command_ringer_mode"]:
            data["command_ringer_mode"] = push_data["command_ringer_mode"]

    async def action_title(self, url: str, retry_timeout: int = 900) -> str | None:
        """Attempt to create a title for mobile action from the TITLE of the web page at the URL"""
        if url in self.action_titles:
            return self.action_titles[url]
        if url in self.action_title_failures:
            # don't retry too often
            if time.time() - self.action_title_failures[url] < retry_timeout:
                _LOGGER.debug("SUPERNOTIFY skipping retry after previous failure to retrieve url title for ", url)
                return None
        try:
            websession: ClientSession = self.context.hass_api.http_session()
            resp: ClientResponse = await websession.get(url, timeout=ClientTimeout(total=5.0))
            body = await resp.content.read()
            # wrap heavy bs4 parsing in a job to avoid blocking the event loop
            html = await self.context.hass_api.create_job(BeautifulSoup, body, "html.parser")
            if html.title and html.title.string:
                self.action_titles[url] = html.title.string
                return html.title.string
        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY failed to retrieve url title at %s: %s", url, e)
            self.action_title_failures[url] = time.time()
        return None

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:  # noqa: ARG002
        if not envelope.target.mobile_app_ids:
            _LOGGER.warning("SUPERNOTIFY No targets provided for mobile_push")
            return False

        # 1. Extract SuperNotify push_* keys; raw_data becomes passthrough-only
        raw_data: dict[str, Any] = dict(envelope.data) if envelope.data else {}
        push_data = self._extract_push_data(raw_data)

        action_groups = envelope.action_groups
        _LOGGER.debug("SUPERNOTIFY notify_mobile: %s -> %s", envelope.title, envelope.target.mobile_app_ids)

        # 2. Build iOS interruption_level
        ios_level = push_data["critical_level_ios"] or IOS_INTERRUPTION_MAP.get(
            envelope.priority or const.PRIORITY_MEDIUM, "active"
        )

        # 3. Start with passthrough data, then layer SuperNotify fields
        data: dict[str, Any] = dict(raw_data)
        category = data.get(ATTR_ACTION_CATEGORY, "general")
        data.setdefault("push", {})
        data["push"]["interruption-level"] = ios_level

        if ios_level == "critical":
            data["push"].setdefault("sound", {})
            data["push"]["sound"].setdefault("name", ATTR_DEFAULT)
            data["push"]["sound"]["critical"] = 1
            data["push"]["sound"].setdefault("volume", 1.0)
            # critical notifications cannot be grouped on iOS
        else:
            media = envelope.media or {}
            camera_entity_id_for_group = media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
            data.setdefault("group", category or camera_entity_id_for_group or "appd")

        # 4. iOS extra fields
        if push_data["subtitle"]:
            data["subtitle"] = push_data["subtitle"]

        # 5. Android-specific fields
        self._apply_android_payload(data, push_data, envelope.priority)

        # 6. Cross-platform: notification tag
        notification_tag = push_data["notification_tag"]
        if notification_tag:
            data["tag"] = notification_tag
        elif push_data["clear_notification"]:
            _LOGGER.warning(
                "SUPERNOTIFY mobile_push: push_clear_notification=True requires push_notification_tag to be set — ignoring"
            )

        # 7. Media: camera entity (grab processed image) + fallback URLs
        media = envelope.media or {}
        camera_entity_id = media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
        clip_url: str | None = self.hass_api.abs_url(media.get(ATTR_MEDIA_CLIP_URL))
        snapshot_url: str | None = self.hass_api.abs_url(media.get(ATTR_MEDIA_SNAPSHOT_URL))

        if camera_entity_id:
            data["entity_id"] = camera_entity_id
            # Retrieve processed camera image via grab_image() pipeline (v1.14.0+)
            image_path = await grab_image(envelope.notification, envelope.delivery, self.context)
            if image_path:
                data["image"] = str(image_path)
        if clip_url:
            data["video"] = clip_url
        if snapshot_url and "image" not in data:
            # Fallback: use pre-computed snapshot URL if grab_image() produced nothing
            data["image"] = snapshot_url

        # 8. Actions: URL-title fetching, snooze action, action groups (unchanged)
        data.setdefault("actions", [])
        for action in envelope.actions:
            app_url: str | None = self.hass_api.abs_url(action.get(ATTR_ACTION_URL))
            if app_url:
                app_url_title = action.get(ATTR_ACTION_URL_TITLE) or await self.action_title(app_url) or "Click for Action"
                action[ATTR_ACTION_URL_TITLE] = app_url_title
            data["actions"].append(action)
        if camera_entity_id:
            data["actions"].append({
                "action": f"SUPERNOTIFY_SNOOZE_EVERYONE_CAMERA_{camera_entity_id}",
                "title": f"Snooze camera notifications for {camera_entity_id}",
                "behavior": "textInput",
                "textInputButtonTitle": "Minutes to snooze",
                "textInputPlaceholder": "60",
            })
        for group, actions in self.context.mobile_actions.items():
            if action_groups is None or group in action_groups:
                data["actions"].extend(actions)
        if not data["actions"]:
            del data["actions"]

        # 9. Dispatch to each mobile target
        action_data = envelope.core_action_data()
        action_data[ATTR_DATA] = data
        clear_notification = bool(push_data["clear_notification"] and notification_tag)
        hits = 0
        for mobile_target in envelope.target.mobile_app_ids:
            full_target = mobile_target if Target.is_notify_entity(mobile_target) else f"notify.{mobile_target}"

            if clear_notification:
                # Override message to "clear_notification" to dismiss same-tag notification on device
                clear_action_data = dict(action_data)
                clear_action_data["message"] = "clear_notification"
                success = await self.call_action(
                    envelope, qualified_action=full_target, action_data=clear_action_data, implied_target=True
                )
            else:
                success = await self.call_action(
                    envelope, qualified_action=full_target, action_data=action_data, implied_target=True
                )

            if success:
                hits += 1
            else:
                simple_target = (
                    mobile_target if not Target.is_notify_entity(mobile_target) else mobile_target.replace("notify.", "")
                )
                _LOGGER.warning("SUPERNOTIFY Failed to send to %s, snoozing for a day", simple_target)
                if self.people_registry:
                    # tie the mobile device back to a recipient for the snoozing API
                    for recipient in self.people_registry.enabled_recipients():
                        for md in recipient.mobile_devices:
                            if md in (simple_target, mobile_target):
                                self.context.snoozer.register_snooze(
                                    CommandType.SNOOZE,
                                    target_type=QualifiedTargetType.MOBILE,
                                    target=simple_target,
                                    recipient_type=RecipientType.USER,
                                    recipient=recipient.entity_id,
                                    snooze_for=timedelta(days=1),
                                    reason="Action Failure",
                                )
        return hits > 0
