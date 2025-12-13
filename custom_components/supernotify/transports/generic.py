import logging
from typing import Any

from homeassistant.components.notify.const import ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET
from homeassistant.const import ATTR_ENTITY_ID  # ATTR_VARIABLES from script.const has import issues

from custom_components.supernotify import (
    OPTION_MESSAGE_USAGE,
    OPTION_SIMPLIFY_TEXT,
    OPTION_STRIP_URLS,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_GENERIC,
)
from custom_components.supernotify.common import ensure_list
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import MessageOnlyPolicy, TargetRequired, TransportConfig
from custom_components.supernotify.transport import (
    Transport,
)

_LOGGER = logging.getLogger(__name__)
DATA_FIELDS_ALLOWED = {
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
}


class GenericTransport(Transport):
    """Call any service, including non-notify ones, like switch.turn_on or mqtt.publish"""

    name = TRANSPORT_GENERIC

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.target_required = TargetRequired.OPTIONAL
        config.delivery_defaults.options = {
            OPTION_SIMPLIFY_TEXT: False,
            OPTION_STRIP_URLS: False,
            OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID],
        }
        return config

    def validate_action(self, action: str | None) -> bool:
        if action is not None and "." in action:
            return True
        _LOGGER.warning("SUPERNOTIFY generic transport must have a qualified action name, e.g. notify.foo")
        return False

    async def deliver(self, envelope: Envelope) -> bool:
        # inputs
        data = envelope.data or {}
        core_action_data = envelope.core_action_data()
        qualified_action = envelope.delivery.action
        domain = qualified_action.split(".", 1)[0] if qualified_action and "." in qualified_action else None
        # outputs
        action_data: dict[str, Any] = {}
        target_data: dict[str, Any] | None = {}
        build_targets: bool = False

        if domain == "notify":
            action_data = core_action_data
            if qualified_action == "notify.send_message":
                # amongst the wild west of notifty handling, at least care for the modern core one
                action_data = core_action_data
                target_data = {ATTR_ENTITY_ID: envelope.target.entity_ids}
            else:
                action_data = core_action_data
                action_data[ATTR_DATA] = data
                build_targets = True
        elif domain == "input_text":
            target_data = {ATTR_ENTITY_ID: envelope.target.entity_ids}
            action_data = {"value": core_action_data[ATTR_MESSAGE]}
        elif domain == "switch":
            target_data = {ATTR_ENTITY_ID: envelope.target.entity_ids}
        elif domain == "mqtt":
            action_data = data
            if "payload" not in action_data:
                action_data["payload"] = envelope.message
                # add `payload:` with empty value for empty topic
        elif domain in ("siren", "light"):
            target_data = {ATTR_ENTITY_ID: envelope.target.entity_ids}
            action_data = data
        elif domain == "rest_command":
            action_data = data
        elif domain == "script":
            if qualified_action in ("script.turn_on", "script.turn_off"):
                target_data = {ATTR_ENTITY_ID: envelope.target.entity_ids}
                action_data["variables"] = core_action_data
                if "variables" in data:
                    action_data["variables"].update(data.pop("variables"))
                action_data["variables"].update(data)
            else:
                action_data = core_action_data
                action_data.update(data)
        else:
            action_data = core_action_data
            action_data.update(data)
            build_targets = True

        if build_targets:
            all_targets: list[str] = []
            for category in ensure_list(envelope.delivery.option(OPTION_TARGET_CATEGORIES)):
                all_targets.extend(envelope.target.for_category(category))
            if len(all_targets) == 1:
                action_data[ATTR_TARGET] = all_targets[0]
            elif len(all_targets) >= 1:
                action_data[ATTR_TARGET] = all_targets

        if domain in DATA_FIELDS_ALLOWED and action_data:
            action_data = {k: v for k, v in action_data.items() if k in DATA_FIELDS_ALLOWED[domain]}

        target_data = target_data or None
        if ATTR_DATA in action_data and not action_data[ATTR_DATA]:
            del action_data[ATTR_DATA]

        return await self.call_action(envelope, qualified_action, action_data=action_data, target_data=target_data)
