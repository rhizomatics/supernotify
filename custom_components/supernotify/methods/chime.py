import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components.group import expand_entity_ids
from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import (  # ATTR_VARIABLES from script.const has import issues
    ATTR_ENTITY_ID,
    CONF_VARIABLES,
)

from custom_components.supernotify import (
    ATTR_DATA,
    ATTR_PRIORITY,
    CONF_DATA,
    CONF_DEVICE_DOMAIN,
    CONF_TARGETS_REQUIRED,
    METHOD_CHIME,
)
from custom_components.supernotify.common import ensure_list
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceEntry

RE_VALID_CHIME = r"(switch|script|group|siren|media_player)\.[A-Za-z0-9_]+"

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA_RESTRICT: dict[str, list[str]] = {
    "media_player": ["data", "entity_id", "media_content_id", "media_content_type", "enqueue", "announce"],
    "switch": ["entity_id"],
    "script": ["data", "variables", "context", "wait"],
    "siren": ["data", "entity_id"],
    "alexa_devices": ["sound", "device_id"],
}  # TODO: source directly from component schema
DEVICE_DOMAINS = ["alexa_devices"]


class ChimeTargetConfig:
    def __init__(
        self,
        target: str,
        tune: str | None = None,
        duration: int | None = None,
        volume: float | None = None,
        data: dict[str, Any] | None = None,
        domain: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.entity_id: str | None = None
        self.device_id: str | None = None
        self.domain: str | None = None
        self.entity_name: str | None = None
        if "." in target:
            self.entity_id = target
            self.domain, self.entity_name = target.split(".", 1)
        else:
            if self.is_device(target):
                self.device_id = target
                self.domain = domain
            else:
                raise ValueError(f"ChimeTargetConfig target must be entity_id or device_id: {target}")
        if kwargs:
            _LOGGER.warning("SUPERNOTIFY ChimeTargetConfig ignoring unexpected args: %s", kwargs)
        self.volume: float | None = volume
        self.tune: str | None = tune
        self.duration: int | None = duration
        self.data: dict[str, Any] | None = data or {}

    def __repr__(self) -> str:
        """Return a developer-oriented string representation of this ChimeTargetConfig"""
        if self.device_id is not None:
            return f"ChimeTargetConfig(device_id={self.device_id})"
        return f"ChimeTargetConfig(entity_id={self.entity_id})"

    @classmethod
    def is_device(cls, target: str) -> bool:
        return re.match(r"^[0-9a-f]{32}$", target) is not None


class ChimeDeliveryMethod(DeliveryMethod):
    method = METHOD_CHIME

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault(CONF_TARGETS_REQUIRED, False)
        # support optional auto discovery
        kwargs.setdefault(CONF_DEVICE_DOMAIN, DEVICE_DOMAINS)
        super().__init__(*args, **kwargs)

    @property
    def chime_aliases(self) -> dict[str, Any]:
        return self.default_options.get("chime_aliases") or {}

    def validate_action(self, action: str | None) -> bool:
        return action is None

    def select_target(self, target: str) -> bool:
        return re.fullmatch(RE_VALID_CHIME, target) is not None or ChimeTargetConfig.is_device(target)

    async def deliver(self, envelope: Envelope) -> bool:
        config = self.delivery_config(envelope.delivery_name)
        data: dict[str, Any] = {}
        data.update(config.get(CONF_DATA) or {})
        data.update(envelope.data or {})
        targets = envelope.targets or []

        # chime_repeat = data.pop("chime_repeat", 1)
        chime_tune: str | None = data.pop("chime_tune", None)
        chime_volume: float | None = data.pop("chime_volume", None)
        chime_duration: int | None = data.pop("chime_duration", None)

        _LOGGER.info(
            "SUPERNOTIFY notify_chime: %s -> %s (delivery: %s, env_data:%s, dlv_data:%s)",
            chime_tune,
            targets,
            envelope.delivery_name,
            envelope.data,
            config.get(CONF_DATA),
        )
        # expand groups
        expanded_targets = {
            e: ChimeTargetConfig(tune=chime_tune, volume=chime_volume, duration=chime_duration, target=e)
            for e in expand_entity_ids(self.hass, targets)
        }
        # resolve and include chime aliases
        expanded_targets.update(self.resolve_tune(chime_tune))  # overwrite and extend

        chimes = 0
        for chime_entity_config in expanded_targets.values():
            _LOGGER.debug("SUPERNOTIFY chime %s: %s", chime_entity_config.entity_id, chime_entity_config.tune)
            action_data = None
            try:
                domain, service, action_data = self.analyze_target(chime_entity_config, data, envelope)
                if domain is not None and service is not None:
                    action_data = self.prune_data(domain, action_data)

                    if await self.call_action(envelope, qualified_action=f"{domain}.{service}", action_data=action_data):
                        chimes += 1
                else:
                    _LOGGER.debug("SUPERNOTIFY Chime skipping incomplete service for %s", chime_entity_config.entity_id)
            except Exception:
                _LOGGER.exception("SUPERNOTIFY Failed to chime %s: %s [%s]", chime_entity_config.entity_id, action_data)
        return chimes > 0

    def prune_data(self, domain: str, data: dict[str, Any]) -> dict[str, Any]:
        pruned: dict[str, Any] = {}
        if data and domain in DATA_SCHEMA_RESTRICT:
            restrict: list[str] = DATA_SCHEMA_RESTRICT.get(domain) or []
            for key in list(data.keys()):
                if key in restrict:
                    pruned[key] = data[key]
        return pruned

    def analyze_target(
        self, target_config: ChimeTargetConfig, data: dict[str, Any], envelope: Envelope
    ) -> tuple[str | None, str | None, dict[str, Any]]:
        if not target_config.entity_id and not target_config.device_id:
            _LOGGER.warning("SUPERNOTIFY Empty chime target")
            return "", None, {}

        domain: str | None = None
        name: str | None = None

        # Alexa Devices use device_id not entity_id for sounds
        if target_config.device_id is not None:
            if target_config.domain is not None:
                domain = target_config.domain
            else:
                # discover domain from device registry
                device_registry = self.context.device_registry()
                if device_registry:
                    device: DeviceEntry | None = device_registry.async_get(target_config.device_id)
                    if device and "alexa_devices" in [d for d, _id in device.identifiers]:
                        domain = "alexa_devices"
                if domain is None:
                    _LOGGER.warning(
                        "SUPERNOTIFY A target that looks like a device_id can't be matched to supported integration: %s",
                        target_config.device_id,
                    )
        elif target_config.entity_id and "." in target_config.entity_id:
            domain, name = target_config.entity_id.split(".", 1)

        action_data: dict[str, Any] = {}
        action: str | None = None

        if domain == "switch":
            action = "turn_on"
            action_data[ATTR_ENTITY_ID] = target_config.entity_id

        elif domain == "siren":
            action = "turn_on"
            action_data[ATTR_ENTITY_ID] = target_config.entity_id
            action_data[ATTR_DATA] = {}
            if target_config.tune:
                action_data[ATTR_DATA]["tone"] = target_config.tune
            if target_config.duration is not None:
                action_data[ATTR_DATA]["duration"] = target_config.duration
            if target_config.volume is not None:
                action_data[ATTR_DATA]["volume_level"] = target_config.volume

        elif domain == "script":
            action_data.setdefault(CONF_VARIABLES, {})
            if target_config.data:
                action_data[CONF_VARIABLES] = target_config.data.get(CONF_VARIABLES, {})
            if data:
                # override data sourced from chime alias with explicit variables in envelope/data
                action_data[CONF_VARIABLES].update(data.get(CONF_VARIABLES, {}))
            action = name
            action_data[CONF_VARIABLES][ATTR_MESSAGE] = envelope.message
            action_data[CONF_VARIABLES][ATTR_TITLE] = envelope.title
            action_data[CONF_VARIABLES][ATTR_PRIORITY] = envelope.priority
            action_data[CONF_VARIABLES]["chime_tune"] = target_config.tune
            action_data[CONF_VARIABLES]["chime_volume"] = target_config.volume
            action_data[CONF_VARIABLES]["chime_duration"] = target_config.duration

        elif domain == "alexa_devices" and target_config.tune:
            action = "send_sound"
            action_data["device_id"] = target_config.device_id
            action_data["sound"] = target_config.tune

        elif domain == "media_player" and target_config.tune:
            if target_config.data:
                action_data.update(target_config.data)
            if data:
                action_data.update(data)
            action = "play_media"
            action_data[ATTR_ENTITY_ID] = target_config.entity_id
            action_data["media_content_type"] = "sound"
            action_data["media_content_id"] = target_config.tune

        else:
            _LOGGER.warning(
                "SUPERNOTIFY No matching chime domain/tune: %s, target: %s, tune: %s",
                domain,
                target_config.entity_id,
                target_config.tune,
            )

        return domain, action, action_data

    def resolve_tune(self, tune_or_alias: str | None) -> dict[str, ChimeTargetConfig]:
        target_configs: dict[str, ChimeTargetConfig] = {}
        if tune_or_alias is not None:
            for domain, alias_config in self.chime_aliases.get(tune_or_alias, {}).items():
                if isinstance(alias_config, str):
                    tune = alias_config
                    alias_config = {}
                else:
                    tune = alias_config.get("tune", tune_or_alias)

                alias_config["tune"] = tune
                alias_config.setdefault("domain", domain)
                alias_config.setdefault("data", {})
                target = alias_config.pop("target", None)

                # pass through variables or data if present
                if target is not None:
                    target_configs.update({t: ChimeTargetConfig(target=t, **alias_config) for t in ensure_list(target)})  # type: ignore
                elif domain in DEVICE_DOMAINS:
                    # bulk apply to all known target devices of this domain
                    bulk_apply = {
                        dev: ChimeTargetConfig(target=dev, **alias_config)  # type: ignore
                        for dev in self.targets
                        if ChimeTargetConfig.is_device(dev)
                        and dev not in target_configs  # don't overwrite existing specific targets
                    }
                    target_configs.update(bulk_apply)
                else:
                    # bulk apply to all known target entities of this domain
                    bulk_apply = {
                        ent: ChimeTargetConfig(target=ent, **alias_config)  # type: ignore
                        for ent in self.targets
                        if ent.startswith(f"{alias_config['domain']}.")
                        and ent not in target_configs  # don't overwrite existing specific targets
                    }
                    target_configs.update(bulk_apply)
        _LOGGER.debug("SUPERNOTIFY method_chime: Resolved tune %s to %s", tune_or_alias, target_configs)
        return target_configs
