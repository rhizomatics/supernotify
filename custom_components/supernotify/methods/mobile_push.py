import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
from homeassistant.components.notify.const import ATTR_DATA

import custom_components.supernotify
from custom_components.supernotify import (
    ATTR_ACTION,
    ATTR_ACTION_CATEGORY,
    ATTR_ACTION_URL,
    ATTR_ACTION_URL_TITLE,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_CLIP_URL,
    ATTR_MEDIA_SNAPSHOT_URL,
    CONF_MOBILE_DEVICES,
    CONF_NOTIFY_ACTION,
    CONF_PERSON,
    METHOD_MOBILE_PUSH,
)
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import CommandType, QualifiedTargetType, RecipientType, Target

RE_VALID_MOBILE_APP = r"mobile_app_[A-Za-z0-9_]+"

_LOGGER = logging.getLogger(__name__)


class MobilePushDeliveryMethod(DeliveryMethod):
    method = METHOD_MOBILE_PUSH

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.action_titles: dict[str, str] = {}

    def select_targets(self, target: Target) -> Target:
        return Target({ATTR_ACTION: [
            e for e in target.actions if re.fullmatch(RE_VALID_MOBILE_APP, e) is not None]})

    @property
    def target_required(self) -> bool:
        # target might be implicit in the service for mobile devices
        return False

    def validate_action(self, action: str | None) -> bool:
        return action is None

    def recipient_target(self, recipient: dict[str, Any]) -> Target | None:
        if CONF_PERSON in recipient:
            actions: list[str] = [md.get(CONF_NOTIFY_ACTION) for md in recipient.get(CONF_MOBILE_DEVICES, [])]
            return Target({ATTR_ACTION: list(filter(None, actions))})
        return None

    async def action_title(self, url: str) -> str | None:
        if url in self.action_titles:
            return self.action_titles[url]
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout=5.0)) as client:
                resp: httpx.Response = await client.get(url, follow_redirects=True, timeout=5)
            html = BeautifulSoup(resp.text, features="html.parser")
            if html.title and html.title.string:
                self.action_titles[url] = html.title.string
                return html.title.string
        except Exception as e:
            _LOGGER.debug("SUPERNOTIFY failed to retrieve url title at %s: %s", url, e)
        return None

    async def deliver(self, envelope: Envelope) -> bool:
        if not envelope.target.actions:
            _LOGGER.warning("SUPERNOTIFY No targets provided for mobile_push")
            return False
        data: dict[str, Any] = envelope.data or {}
        # TODO: category not passed anywhere
        category = data.get(ATTR_ACTION_CATEGORY, "general")
        action_groups = envelope.action_groups

        _LOGGER.debug("SUPERNOTIFY notify_mobile: %s -> %s", envelope.title, envelope.target.actions)

        media = envelope.media or {}
        camera_entity_id = media.get(ATTR_MEDIA_CAMERA_ENTITY_ID)
        clip_url: str | None = self.abs_url(media.get(ATTR_MEDIA_CLIP_URL))
        snapshot_url: str | None = self.abs_url(media.get(ATTR_MEDIA_SNAPSHOT_URL))
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
            case _:
                push_priority = "active"
                _LOGGER.warning("SUPERNOTIFY Unexpected priority %s", envelope.priority)

        data.setdefault("actions", [])
        data.setdefault("push", {})
        data["push"]["interruption-level"] = push_priority
        if push_priority == "critical":
            data["push"].setdefault("sound", {})
            data["push"]["sound"].setdefault("name", "default")
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
            app_url: str | None = self.abs_url(action.get(ATTR_ACTION_URL))
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
        for mobile_target in envelope.target.actions:
            full_target = mobile_target if mobile_target.startswith("notify.") else f"notify.{mobile_target}"
            if await self.call_action(envelope, qualified_action=full_target, action_data=action_data):
                hits += 1
            else:
                simple_target = (
                    mobile_target if not mobile_target.startswith("notify.") else mobile_target.replace("notify.", "")
                )
                _LOGGER.warning("SUPERNOTIFY Failed to send to %s, snoozing for a day", simple_target)
                if self.context.people_registry:
                    # somewhat hacky way to tie the mobile device back to a recipient to please the snoozing api
                    for recipient in self.context.people_registry.people.values():
                        for md in recipient.get(CONF_MOBILE_DEVICES, []):
                            if md.get(CONF_NOTIFY_ACTION) in (simple_target, mobile_target):
                                self.context.snoozer.register_snooze(
                                    CommandType.SNOOZE,
                                    target_type=QualifiedTargetType.ACTION,
                                    target=simple_target,
                                    recipient_type=RecipientType.USER,
                                    recipient=recipient[CONF_PERSON],
                                    snooze_for=24 * 60 * 60,
                                    reason="Action Failure",
                                )
        return hits > 0
