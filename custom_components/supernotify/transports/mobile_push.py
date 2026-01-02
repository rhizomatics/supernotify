import logging
import time
from datetime import timedelta
from typing import Any

from aiohttp import ClientResponse, ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from homeassistant.components.notify.const import ATTR_DATA

import custom_components.supernotify
from custom_components.supernotify import (
    ATTR_ACTION_CATEGORY,
    ATTR_ACTION_URL,
    ATTR_ACTION_URL_TITLE,
    ATTR_DEFAULT,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_MOBILE_APP_ID,
    OPTION_DEVICE_DISCOVERY_ENABLED,
    OPTION_DEVICE_DOMAIN,
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_MOBILE_PUSH,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.hass_api import HomeAssistantAPI
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
from custom_components.supernotify.transport import (
    Transport,
)

_LOGGER = logging.getLogger(__name__)


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
            OPTION_DEVICE_DISCOVERY_ENABLED: True,
            OPTION_DEVICE_DOMAIN: ["mobile_app"],
        }
        return config

    def auto_configure(self, hass_api: HomeAssistantAPI) -> DeliveryConfig | None:  # noqa: ARG002
        return self.delivery_defaults

    def validate_action(self, action: str | None) -> bool:
        return action is None

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
        data: dict[str, Any] = envelope.data or {}
        # TODO: category not passed anywhere
        category = data.get(ATTR_ACTION_CATEGORY, "general")
        action_groups = envelope.action_groups

        _LOGGER.debug("SUPERNOTIFY notify_mobile: %s -> %s", envelope.title, envelope.target.mobile_app_ids)

        media = envelope.media or {}
        camera_entity_id = media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
        clip_url: str | None = self.hass_api.abs_url(media.get(ATTR_MEDIA_CLIP_URL))
        snapshot_url: str | None = self.hass_api.abs_url(media.get(ATTR_MEDIA_SNAPSHOT_URL))
        # options = data.get(CONF_OPTIONS, {})

        match envelope.priority:
            case custom_components.supernotify.PRIORITY_CRITICAL:
                push_priority = "critical"
            case custom_components.supernotify.PRIORITY_HIGH:
                push_priority = "time-sensitive"
            case custom_components.supernotify.PRIORITY_MEDIUM:
                push_priority = "active"
            case custom_components.supernotify.PRIORITY_LOW:
                push_priority = "passive"
            case custom_components.supernotify.PRIORITY_MINIMUM:
                push_priority = "passive"
            case _:
                push_priority = "active"
                _LOGGER.warning("SUPERNOTIFY Unexpected priority %s", envelope.priority)

        data.setdefault("actions", [])
        data.setdefault("push", {})
        data["push"]["interruption-level"] = push_priority
        if push_priority == "critical":
            data["push"].setdefault("sound", {})
            data["push"]["sound"].setdefault("name", ATTR_DEFAULT)
            data["push"]["sound"]["critical"] = 1
            data["push"]["sound"].setdefault("volume", 1.0)
        else:
            # critical notifications can't be grouped on iOS
            category = category or camera_entity_id or "appd"
            data.setdefault("group", category)

        if camera_entity_id:
            data["entity_id"] = camera_entity_id
            # data['actions'].append({'action':'URI','title':'View Live','uri':'/cameras/%s' % device}
        if clip_url:
            data["video"] = clip_url
        if snapshot_url:
            data["image"] = snapshot_url

        data.setdefault("actions", [])
        for action in envelope.actions:
            app_url: str | None = self.hass_api.abs_url(action.get(ATTR_ACTION_URL))
            if app_url:
                app_url_title = action.get(ATTR_ACTION_URL_TITLE) or self.action_title(app_url) or "Click for Action"
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
        action_data = envelope.core_action_data()
        action_data[ATTR_DATA] = data
        hits = 0
        for mobile_target in envelope.target.mobile_app_ids:
            full_target = mobile_target if Target.is_notify_entity(mobile_target) else f"notify.{mobile_target}"
            if await self.call_action(envelope, qualified_action=full_target, action_data=action_data, implied_target=True):
                hits += 1
            else:
                simple_target = (
                    mobile_target if not Target.is_notify_entity(mobile_target) else mobile_target.replace("notify.", "")
                )
                _LOGGER.warning("SUPERNOTIFY Failed to send to %s, snoozing for a day", simple_target)
                if self.people_registry:
                    # somewhat hacky way to tie the mobile device back to a recipient to please the snoozing api
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
