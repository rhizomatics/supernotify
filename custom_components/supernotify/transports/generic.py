from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE

# ATTR_VARIABLES from script.const has import issues
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.supernotify.common import ensure_list
from custom_components.supernotify.const import (
    ATTR_ACTION_URL,
    ATTR_ACTIONS,
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_PRIORITY,
    OPTION_DATA_KEYS_SELECT,
    OPTION_GENERIC_DOMAIN_STYLE,
    OPTION_MESSAGE_USAGE,
    OPTION_RAW,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    PRIORITY_MINIMUM,
    PRIORITY_VALUES,
    TRANSPORT_GENERIC,
)
from custom_components.supernotify.model import (
    DataFilter,
    DebugTrace,
    MessageOnlyPolicy,
    Target,
    TargetRequired,
    TransportConfig,
    TransportFeature,
)
from custom_components.supernotify.transport import (
    Transport,
)

if TYPE_CHECKING:
    from custom_components.supernotify.delivery import Delivery
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.hass_api import HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)
"""
Replaced by reuse of original service schema to prune out fields

DATA_FIELDS_ALLOWED_BY_DOMAIN = {
    "light": [
        "transition",
        "rgb_color",
        "color_temp_kelvin",
        "brightness_pct",
        "brightness_step_pct",
        "effect",
        "rgbw_color",
        "rgbww_color",
        "color_name",
        "hs_color",
        "xy_color",
        "color_temp",
        "brightness",
        "brightness_step",
        "white",
        "profile",
        "flash",
    ],
    "siren": ["tone", "duration", "volume_level"],
    "mqtt": ["topic", "payload", "evaluate_payload", "qos", "retain"],
    "script": ["variables", "wait", "wait_template"],
    "ntfy": [
        "title",
        "message",
        "markdown",
        "tags",
        "priority",
        "click",
        "delay",
        "attach",
        "attach_file",
        "filename",
        "email",
        "call",
        "icon",
        "action",
        "sequence_id",
    ],
    "tts": ["cache", "options", "message", "language", "media_player_entity_id", "entity_id", "target"],
} """


class GenericTransport(Transport):
    """Call any service, including non-notify ones, like switch.turn_on or mqtt.publish"""

    name = TRANSPORT_GENERIC

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature.MESSAGE | TransportFeature.TITLE

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.target_required = TargetRequired.OPTIONAL
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_RAW: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_DATA_KEYS_SELECT: None,
            OPTION_GENERIC_DOMAIN_STYLE: None,
        }
        return config

    def validate_action(self, action: str | None) -> bool:
        if action is not None and "." in action:
            return True
        _LOGGER.warning("SUPERNOTIFY Generic transport must have a qualified action name, e.g. notify.foo")
        return False

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        # inputs
        data: dict[str, Any] = envelope.data or {}
        core_action_data: dict[str, Any] = envelope.core_action_data(force_message=False)
        raw_mode: bool = envelope.delivery.options.get(OPTION_RAW, False)
        qualified_action: str | None = envelope.delivery.action
        split_action = (
            qualified_action.split(".", 1) if qualified_action and "." in qualified_action else [None, qualified_action]
        )
        domain: str | None = split_action[0]
        service: str | None = split_action[1]

        equiv_domain: str | None = domain
        if envelope.delivery.options.get(OPTION_GENERIC_DOMAIN_STYLE):
            equiv_domain = envelope.delivery.options.get(OPTION_GENERIC_DOMAIN_STYLE)
            _LOGGER.debug("SUPERNOTIFY Handling %s generic message as if it was %s", domain, equiv_domain)

        # outputs
        action_data: dict[str, Any] = {}
        target_data: dict[str, Any] | None = {}
        build_targets: bool = False
        prune_data: bool = True
        mini_envelopes: list[MiniEnvelope] = []  # only used for script and ntfy

        if raw_mode:
            action_data = core_action_data
            action_data.update(data)
            build_targets = True
        elif equiv_domain == "notify":
            action_data = core_action_data
            if qualified_action == "notify.send_message":
                # amongst the wild west of notifty handling, at least care for the modern core one
                action_data = core_action_data
                target_data = {ATTR_ENTITY_ID: envelope.target.domain_entity_ids(domain)}
                prune_data = False
            else:
                action_data = core_action_data
                action_data[ATTR_DATA] = data
                build_targets = True
        elif equiv_domain == "input_text":
            target_data = {ATTR_ENTITY_ID: envelope.target.domain_entity_ids(domain)}
            if "value" in data:
                action_data = {"value": data["value"]}
            else:
                action_data = {"value": core_action_data[ATTR_MESSAGE]}
        elif equiv_domain == "switch":
            target_data = {ATTR_ENTITY_ID: envelope.target.domain_entity_ids(domain)}
        elif equiv_domain == "mqtt":
            action_data = data
            if "payload" not in action_data:
                action_data["payload"] = envelope.message
                # add `payload:` with empty value for empty topic
        elif equiv_domain == "tts":
            action_data = core_action_data
            action_data.update(data)
            build_targets = True
        elif equiv_domain == "notify_events":
            mini_envelopes.extend(notify_events(envelope.message, envelope.title, core_action_data, data, envelope.delivery))
        elif qualified_action == "ntfy.publish":
            mini_envelopes.extend(ntfy(core_action_data, data, envelope.target, envelope.delivery, self.hass_api))
        elif equiv_domain in ("siren", "light"):
            target_data = {ATTR_ENTITY_ID: envelope.target.domain_entity_ids(domain)}
            action_data = data
        elif equiv_domain == "rest_command":
            action_data = data
        elif equiv_domain == "script":
            mini_envelopes.extend(
                script(qualified_action, core_action_data, data, envelope.target, envelope.delivery, self.hass_api)
            )
        else:
            action_data = core_action_data
            action_data.update(data)
            build_targets = True

        if mini_envelopes:
            results: list[bool] = [
                await self.call_action(
                    envelope, qualified_action, action_data=mini_envelope.action_data, target_data=mini_envelope.target_data
                )
                for mini_envelope in mini_envelopes
            ]
            return all(results)

        if build_targets:
            all_targets: list[str] = []
            if OPTION_TARGET_CATEGORIES in envelope.delivery.options:
                for category in ensure_list(envelope.delivery.options.get(OPTION_TARGET_CATEGORIES, [])):
                    all_targets.extend(envelope.target.for_category(category))
            else:
                all_targets = envelope.target.resolved_targets()
            if len(all_targets) == 1:
                action_data[ATTR_TARGET] = all_targets[0]
            elif len(all_targets) >= 1:
                action_data[ATTR_TARGET] = all_targets

        if prune_data and action_data:
            action_data = envelope.customize_data(action_data)
        if not raw_mode and domain and service:
            # use the service schema to remove unsupported fields or force type
            action_data = self.context.hass_api.coerce_schema(domain, service, action_data)

        return await self.call_action(envelope, qualified_action, action_data=action_data, target_data=target_data or None)


@dataclass
class MiniEnvelope:
    action_data: dict[str, Any] = field(default_factory=dict)
    target_data: dict[str, Any] | None = None


def script(
    qualified_action: str | None,
    core_action_data: dict[str, Any],
    data: dict[str, Any],
    target: Target,
    delivery: Delivery,
    hass_api: HomeAssistantAPI,
) -> list[MiniEnvelope]:
    """Customize `data` for script integration"""
    results: list[MiniEnvelope] = []
    if qualified_action in ("script.turn_on", "script.turn_off"):
        action_data = {}
        action_data["variables"] = core_action_data
        if "variables" in data:
            action_data["variables"].update(data.pop("variables"))
        action_data["variables"].update(data)
        action_data = hass_api.coerce_schema("script", qualified_action.replace("script.", ""), action_data)
        results.append(MiniEnvelope(action_data=action_data, target_data={ATTR_ENTITY_ID: target.domain_entity_ids("script")}))
    else:
        action_data = core_action_data
        action_data.update(data)
        results.append(MiniEnvelope(action_data=action_data))

    return results


def ntfy(
    core_action_data: dict[str, Any],
    data: dict[str, Any],
    target: Target,
    delivery: Delivery,
    hass_api: HomeAssistantAPI,
) -> list[MiniEnvelope]:
    """Customize `data` for ntfy integration"""
    results: list[MiniEnvelope] = []
    action_data: dict[str, Any] = dict(core_action_data)
    action_data.update(data)
    action_data = hass_api.coerce_schema("ntfy", "publish", action_data)

    if ATTR_PRIORITY in action_data and action_data[ATTR_PRIORITY] in PRIORITY_VALUES:
        action_data[ATTR_PRIORITY] = PRIORITY_VALUES.get(action_data[ATTR_PRIORITY], 3)

    media = action_data.pop(ATTR_MEDIA, {})
    if media and media.get(ATTR_MEDIA_SNAPSHOT_URL) and "attach" not in action_data:
        action_data["attach"] = media.get(ATTR_MEDIA_SNAPSHOT_URL)
    actions = action_data.pop(ATTR_ACTIONS, [])
    if len(actions) > 0:
        first_action = actions[0]
        if first_action.get(ATTR_ACTION_URL) and "click" not in action_data:
            action_data["click"] = first_action.get(ATTR_ACTION_URL)

    if target.email and "email" not in action_data:
        for email in target.email:
            call_data: dict[str, Any] = dict(action_data)
            if len(results) == 1 and len(target.email) == 1:
                results[0].action_data["email"] = email
            else:
                call_data["email"] = email
                results.append(MiniEnvelope(action_data=call_data))
    if target.phone and "call" not in action_data:
        for phone in target.phone:
            call_data = dict(action_data)
            if len(results) == 1 and len(target.phone) == 1:
                results[0].action_data["call"] = phone
            else:
                call_data["call"] = phone
                results.append(MiniEnvelope(action_data=call_data))
    notify_entities = target.domain_entity_ids(NOTIFY_DOMAIN)

    rules = delivery.options.get(OPTION_DATA_KEYS_SELECT)
    action_data = DataFilter(rules).apply(action_data)

    if not results or notify_entities:
        if len(results) == 1:
            results[0].target_data = {"entity_id": notify_entities}
        else:
            results.append(MiniEnvelope(action_data=dict(action_data), target_data={"entity_id": notify_entities}))

    return results


def notify_events(
    message: str | None,
    title: str | None,
    core_action_data: dict[str, Any],
    data: dict[str, Any],
    delivery: Delivery,
) -> list[MiniEnvelope]:
    """Customize `data` for notify_events integration"""
    results: list[MiniEnvelope] = []
    input_data: dict[str, Any] = dict(core_action_data)
    input_data.update(data)

    action_data: dict[str, Any] = {}
    action_data[ATTR_MESSAGE] = message
    priority_mapping: dict[str, str] = {
        PRIORITY_MINIMUM: "lowest",
        PRIORITY_LOW: "low",
        PRIORITY_MEDIUM: "normal",
        PRIORITY_HIGH: "high",
        PRIORITY_CRITICAL: "highest",
    }
    if title:
        action_data.setdefault(ATTR_DATA, {})
        action_data[ATTR_DATA][ATTR_TITLE] = title

    if ATTR_DATA in input_data:
        # notify_events is schema-less for action
        action_data[ATTR_DATA] = input_data[ATTR_DATA]

    if ATTR_PRIORITY in input_data and input_data[ATTR_PRIORITY] in PRIORITY_VALUES:
        action_data.setdefault(ATTR_DATA, {})
        action_data[ATTR_DATA][ATTR_PRIORITY] = priority_mapping.get(input_data[ATTR_PRIORITY])
    elif ATTR_PRIORITY in input_data and input_data[ATTR_PRIORITY] in priority_mapping.values():
        action_data.setdefault(ATTR_DATA, {})
        action_data[ATTR_DATA][ATTR_PRIORITY] = input_data[ATTR_PRIORITY]

    if "token" in input_data:
        action_data.setdefault(ATTR_DATA, {})
        action_data[ATTR_DATA]["token"] = input_data["token"]
    if "level" in input_data:
        action_data.setdefault(ATTR_DATA, {})
        action_data[ATTR_DATA]["level"] = input_data["level"]

    if input_data.get(ATTR_MEDIA, {}).get(ATTR_MEDIA_SNAPSHOT_URL) and "images" not in input_data:
        action_data.setdefault(ATTR_DATA, {})
        action_data[ATTR_DATA].setdefault("images", [])
        action_data[ATTR_DATA]["images"].append({"url": input_data.get(ATTR_MEDIA, {}).get(ATTR_MEDIA_SNAPSHOT_URL)})

    rules = delivery.options.get(OPTION_DATA_KEYS_SELECT)
    action_data = DataFilter(rules).apply(action_data)
    results.append(MiniEnvelope(action_data=dict(action_data)))

    return results
