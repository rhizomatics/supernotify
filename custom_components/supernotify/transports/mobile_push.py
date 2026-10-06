"""Mobile App Companion transport for SuperNotify.

Sends push notifications to HA Companion App on iOS and Android devices.
Supports per-device delivery with automatic snooze on failure.

Priority mapping (auto, overridable via push_critical_level_ios):
    critical  → iOS: interruption_level=critical
                Android: ttl=0, priority=high, channel=alarm_stream (sounds through Do Not Disturb
                and silent mode, unless the data already sets a `channel`)
    high      → iOS: interruption_level=time-sensitive
    medium    → iOS: interruption_level=active    (default)
    low       → iOS: interruption_level=passive
    minimum   → iOS: interruption_level=passive

New data keys (all optional):
    mobile_push_critical_level      str   iOS interruption_level override
                                      ("passive","active","time-sensitive","critical")
                                      If omitted, auto-mapped from SuperNotify priority.
    mobile_push_critical_ttl        int   Android FCM TTL in ms (0=no caching/instant).
                                      Auto-set to 0 for critical priority if not set.
    mobile_push_critical_priority   str   Android FCM priority override ("high" or "normal").
                                      Auto-set to "high" for critical priority if not set.
    mobile_push_critical_channel    str   Android channel for critical priority, "alarm_stream" if not set.
                                      Set to false to leave the channel alone.
    mobile_push_subtitle            str   iOS subtitle (line between title and message, iOS 10+)
    mobile_push_group               str   Notification group for visual stacking (iOS thread-id / Android group).
                                      Falls back to the camera entity id if there's a camera image,
                                      otherwise left unset (notification appears individually).
    mobile_push_notification_tag    str   Notification tag for replacement (iOS) / grouping (Android)
    mobile_push_clear_notification  bool  Send clear_notification to dismiss previous same-tag notification.
                                      Requires push_notification_tag to be set.
    mobile_push_tts_text            str   Android: text read aloud by the phone (Android 8+), sent as its own
                                      `message: TTS` call after the notification, on the alarm stream at
                                      full volume for critical. If omitted, push TTS is not activated.
    mobile_push_tts_delay           int   Seconds between the notification and its TTS, so the notification's
                                      own sound isn't cut off (default 5, 0 for straight away).
    mobile_push_tts_locale          str   BCP-47 language for TTS (e.g. "it-IT", "en-US").
                                      Only used when push_tts_text is set.
    mobile_push_tts_engine          str   TTS engine package (e.g. "com.google.android.tts").
                                      Only used when push_tts_text is set.
    mobile_push_command_screen_on   bool  Android: turn on device screen on delivery (Android 8+),
                                      or "keep_screen_on"
    mobile_push_command_dnd         str   Android: change Do Not Disturb ("alarms_only","priority_only",
                                      "total_silence","off")
    mobile_push_command_ringer_mode str   Android: change ringer mode ("normal","silent","vibrate")
                                      The command_* keys are each sent as their own `message: command_...`
                                      call before the notification, as the companion app takes them.
    mobile_push_channel_override    str   Android notification channel override (e.g. "alarm","general")
    mobile_push_alarm_stream        bool  Android: use the alarm_stream channel, which sounds through
                                      Do Not Disturb and silent mode
    mobile_push_alarm_stream_max    bool  Android: kept for compatibility, same as mobile_push_alarm_stream -
                                      the companion app only supports alarm_stream_max for TTS

"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from aiohttp import ClientResponse, ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from homeassistant.components.notify.const import ATTR_DATA
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify import const
from custom_components.supernotify.const import (
    ATTR_ACTION_URL,
    ATTR_ACTION_URL_TITLE,
    ATTR_DEFAULT,
    ATTR_IMAGE,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_MOBILE_APP_ID,
    ATTR_VIDEO,
    MANUFACTURER_APPLE,
    TRANSPORT_MOBILE_PUSH,
)
from custom_components.supernotify.media_grab import select_avail_camera
from custom_components.supernotify.model import (
    CommandType,
    DebugTrace,
    MessageOnlyPolicy,
    QualifiedTargetType,
    RecipientType,
    SelectionRule,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.options import (
    MEDIA_OPTIONS,
    OPTION_DATA_KEYS_SELECT,
    OPTION_DEVICE_DISCOVERY,
    OPTION_DEVICE_DOMAIN,
    OPTION_DEVICE_MODEL_SELECT,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    DeliveryOption,
)
from custom_components.supernotify.target import Target, TargetEntityCategory
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI, TrackedDeviceDetails

_LOGGER = logging.getLogger(__name__)

# iOS interruption_level mapping from SuperNotify priority
IOS_INTERRUPTION_MAP: dict[str, str] = {
    const.PRIORITY_CRITICAL: "critical",
    const.PRIORITY_HIGH: "time-sensitive",
    const.PRIORITY_MEDIUM: "active",
    const.PRIORITY_LOW: "passive",
    const.PRIORITY_MINIMUM: "passive",
}

# Android FCM TTL auto-set for critical priority (0 = instant, no FCM caching)
ANDROID_CRITICAL_TTL = 0
# Android FCM priority and channel auto-set for critical priority - what the companion app
# documents for critical notifications, alarm_stream being what gets through Do Not Disturb
ANDROID_CRITICAL_PRIORITY = "high"
ANDROID_ALARM_STREAM_CHANNEL = "alarm_stream"
# seconds between a notification and its TTS on Android - started together, the TTS cuts off the
# notification's own sound
ANDROID_TTS_DELAY = 5


class MobilePushTransport(Transport):
    name = TRANSPORT_MOBILE_PUSH
    declared_options: ClassVar[list[DeliveryOption]] = [
        *MEDIA_OPTIONS,
        DeliveryOption(
            OPTION_DATA_KEYS_SELECT,
            "Prune the data block by including/excluding values or by regex pattern",
            value_type=SelectionRule,
        ),
    ]

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
        config = super().default_config
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_DEVICE_DISCOVERY: False,
            OPTION_DATA_KEYS_SELECT: None,
            OPTION_DEVICE_DOMAIN: ["mobile_app"],
        }
        return config

    @property
    def unique_target_categories(self) -> list[str | TargetEntityCategory]:
        return [ATTR_MOBILE_APP_ID]

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        return hass_api.find_config_entry_data("mobile_app") is not None

    def build_standard_deliveries(self, hass_api: HomeAssistantAPI) -> dict[str, ConfigType]:
        return {self.name: {}}

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
            "critical_level_ios": raw_data.pop("mobile_push_critical_level", None),
            "subtitle": raw_data.pop("mobile_push_subtitle", None),
            # Android critical
            "critical_ttl": raw_data.pop("mobile_push_critical_ttl", None),
            "critical_android_priority": raw_data.pop("mobile_push_critical_priority", None),
            "channel_override": raw_data.pop("mobile_push_channel_override", None),
            "critical_channel": raw_data.pop("mobile_push_critical_channel", ANDROID_ALARM_STREAM_CHANNEL),
            "alarm_stream": raw_data.pop("mobile_push_alarm_stream", False),
            "alarm_stream_max": raw_data.pop("mobile_push_alarm_stream_max", False),
            # Android TTS
            "tts_text": raw_data.pop("mobile_push_tts_text", None),
            "tts_locale": raw_data.pop("mobile_push_tts_locale", None),
            "tts_engine": raw_data.pop("mobile_push_tts_engine", None),
            "tts_delay": raw_data.pop("mobile_push_tts_delay", ANDROID_TTS_DELAY),
            # Android Notification Commands
            "command_screen_on": raw_data.pop("mobile_push_command_screen_on", None),
            "command_dnd": raw_data.pop("mobile_push_command_dnd", None),
            "command_ringer_mode": raw_data.pop("mobile_push_command_ringer_mode", None),
            # Cross-platform
            "group": raw_data.pop("mobile_push_group", None),
            "notification_tag": raw_data.pop("mobile_push_notification_tag", None),
            "clear_notification": raw_data.pop("mobile_push_clear_notification", False),
        }

    def _android_payload(
        self,
        push_data: dict[str, Any],
        priority: str | None,
        channel_given: bool = False,
    ) -> dict[str, Any]:
        """Apply Android-specific fields to the notification data dict.

        Android fields live flat in data{}, not inside the push{} sub-dict. `channel_given` is when the
        pass-through data already has a `channel`, which then isn't replaced.
        """
        android_data: dict[str, Any] = {}
        critical: bool = priority == const.PRIORITY_CRITICAL
        # Channel override (Android 8+, determines sound/vibration/LED)
        if push_data["channel_override"]:
            android_data["channel"] = push_data["channel_override"]
        elif push_data["alarm_stream"] or push_data["alarm_stream_max"]:
            # the companion app takes the alarm stream as a channel, not a flag of its own
            android_data["channel"] = ANDROID_ALARM_STREAM_CHANNEL
        elif critical and push_data["critical_channel"] and not channel_given:
            android_data["channel"] = push_data["critical_channel"]

        # FCM TTL: auto-set to 0 for critical (instant delivery, no FCM caching)
        if push_data["critical_ttl"] is not None:
            android_data["ttl"] = push_data["critical_ttl"]
        elif priority == const.PRIORITY_CRITICAL:
            android_data["ttl"] = ANDROID_CRITICAL_TTL

        # FCM priority: high for critical, so a dozing phone gets it straight away
        if push_data["critical_android_priority"] is not None:
            android_data["priority"] = push_data["critical_android_priority"]
        elif critical:
            android_data["priority"] = ANDROID_CRITICAL_PRIORITY

        return android_data

    def _android_extra_calls(
        self, push_data: dict[str, Any], priority: str | None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Notification commands and TTS, which the companion app takes as the `message` of a call of
        their own rather than as notification data - commands to go before the notification, so the
        screen is on or Do Not Disturb off when it arrives, and TTS after it."""
        # a call without high priority can wait until the phone is unlocked - a critical's TTS would then be
        # spoken late, maybe twice - so for critical these go as fast as the notification itself
        urgent: dict[str, Any] = (
            {"ttl": ANDROID_CRITICAL_TTL, "priority": ANDROID_CRITICAL_PRIORITY} if priority == const.PRIORITY_CRITICAL else {}
        )
        before: list[dict[str, Any]] = []
        for key in ("command_dnd", "command_ringer_mode", "command_screen_on"):
            value = push_data[key]
            if value:
                before.append({"message": key, ATTR_DATA: ({} if value is True else {"command": value}) | urgent})
        after: list[dict[str, Any]] = []
        if push_data["tts_text"]:
            tts_data: dict[str, Any] = {"tts_text": push_data["tts_text"], **urgent}
            if push_data["alarm_stream_max"] or priority == const.PRIORITY_CRITICAL:
                # at full volume for critical - on a watch the alarm volume can be too low to hear,
                # and the companion app puts the volume back afterwards
                tts_data["media_stream"] = "alarm_stream_max"
            elif push_data["alarm_stream"]:
                tts_data["media_stream"] = ANDROID_ALARM_STREAM_CHANNEL
            if push_data["tts_locale"]:
                tts_data["tts_text_language"] = push_data["tts_locale"]
            if push_data["tts_engine"]:
                tts_data["tts_engine"] = push_data["tts_engine"]
            after.append({"message": "TTS", ATTR_DATA: tts_data})
        return before, after

    async def action_title(self, url: str, retry_timeout: int = 900) -> str | None:
        """Attempt to create a title for mobile action from the TITLE of the web page at the URL"""
        if url in self.action_titles:
            return self.action_titles[url]
        if url in self.action_title_failures and time.time() - self.action_title_failures[url] < retry_timeout:
            # don't retry too often
            _LOGGER.debug("SUPERNOTIFY Skipping retry after previous failure to retrieve url title for %s", url)
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
            _LOGGER.warning("SUPERNOTIFY Failed to retrieve url title at %s: %s", url, e)
            self.action_title_failures[url] = time.time()
        return None

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
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
        ios_data: dict[str, Any] = {}

        ios_data.setdefault("push", {})
        ios_data["push"]["interruption-level"] = ios_level

        if ios_level == "critical":
            ios_data["push"].setdefault("sound", {})
            ios_data["push"]["sound"].setdefault("name", ATTR_DEFAULT)
            ios_data["push"]["sound"]["critical"] = 1
            ios_data["push"]["sound"].setdefault("volume", 1.0)
            # critical notifications cannot be grouped on iOS
        else:
            media = envelope.media or {}
            camera_entity_id_for_group = media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
            group = push_data["group"] or camera_entity_id_for_group
            # unlike `tag`, an unset `group` leaves notifications ungrouped on the device
            # (companion app default) rather than forcing them all into a shared bucket
            if group:
                data.setdefault("group", group)

        # 4. iOS extra fields

        if push_data["subtitle"]:
            ios_data["subtitle"] = push_data["subtitle"]

        # 5. Android-specific fields
        android_data: dict[str, Any] = self._android_payload(push_data, envelope.priority, channel_given="channel" in raw_data)
        android_before, android_after = self._android_extra_calls(push_data, envelope.priority)

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
        # Remove self.hass_api.abs_url for clip_url and snapshot_url
        clip_url: str | None = media.get(ATTR_MEDIA_CLIP_URL)
        snapshot_url: str | None = media.get(ATTR_MEDIA_SNAPSHOT_URL)

        if camera_entity_id:
            image_path = await envelope.grab_image()
            if image_path:
                image_url = await self.context.media_storage.share_path(image_path)
                data[ATTR_IMAGE] = image_url or str(image_path)
            else:
                # fall back to letting device take the image, but only from a camera that's up,
                # since one that's switched off or unavailable would only show a broken image.
                # camera_entity_id itself already failed the grab above - exclude it here, since
                # a camera disabled at the device (rather than truly unavailable) won't show that
                # in its entity state, so re-offering it would just repeat the same failed fetch
                available_camera_entity_id = select_avail_camera(
                    self.hass_api, self.context.cameras, camera_entity_id, exclude_primary=True
                )
                if available_camera_entity_id:
                    data["entity_id"] = available_camera_entity_id
                else:
                    _LOGGER.info("SUPERNOTIFY mobile_push: no available camera for %s, sending without image", camera_entity_id)
        if clip_url:
            data[ATTR_VIDEO] = clip_url

        if snapshot_url and ATTR_IMAGE not in data:
            # Fallback: use pre-computed snapshot URL if grab_image() produced nothing
            data[ATTR_IMAGE] = snapshot_url

        # 8. Actions: URL-title fetching, snooze action, action groups (unchanged)
        if "actions" in data and not isinstance(data["actions"], list):
            _LOGGER.warning(
                "SUPERNOTIFY mobile_push: data.actions must be a list of action objects, ignoring invalid value %s",
                data["actions"],
            )
            data["actions"] = []
        else:
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
        clear_notification = bool(push_data["clear_notification"] and notification_tag)
        model_filter = SelectionRule(envelope.delivery.options.get(OPTION_DEVICE_MODEL_SELECT))
        hits = 0
        tts_pending: list[tuple[str, dict[str, Any]]] = []

        for mobile_target in envelope.target.mobile_app_ids:
            full_target = mobile_target if Target.is_notify_entity(mobile_target) else f"notify.{mobile_target}"
            mobile_info: TrackedDeviceDetails | None = self.context.hass_api.mobile_app_by_id(mobile_target)
            if mobile_info is not None and not model_filter.match(mobile_info.model):
                _LOGGER.debug("SUPERNOTIFY Skipping %s, model %s excluded by delivery filter", mobile_target, mobile_info.model)
                continue

            # fresh copy per target - customize_data below may prune `data` down to nothing
            # (e.g. an Android target with no android/ios fields to merge in), and that must
            # not carry over and clobber the next target's action_data
            target_data = dict(data)
            is_android: bool = mobile_info is not None and mobile_info.manufacturer != MANUFACTURER_APPLE
            if mobile_info is None:
                target_data.update(android_data)
                target_data.update(ios_data)
                if android_before or android_after:
                    # an iPhone would show a command or TTS call as a notification saying "command_dnd"
                    _LOGGER.debug(
                        "SUPERNOTIFY mobile_push: not sending Android commands/TTS to unknown device %s", mobile_target
                    )
            elif is_android:  # TODO Make this os_name based
                target_data.update(android_data)
            else:
                target_data.update(ios_data)
            if is_android:
                for extra in android_before:
                    await self.call_action(envelope, qualified_action=full_target, action_data=dict(extra), implied_target=True)

            action_data = envelope.core_action_data()
            action_data[ATTR_DATA] = target_data
            action_data = envelope.customize_data(action_data)

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

            if success and is_android:
                tts_pending.extend((full_target, dict(extra)) for extra in android_after)

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
        if tts_pending:
            # one wait for all the devices, after every notification has gone
            if push_data["tts_delay"]:
                await asyncio.sleep(push_data["tts_delay"])
            for full_target, extra in tts_pending:
                await self.call_action(envelope, qualified_action=full_target, action_data=extra, implied_target=True)
        return hits > 0
