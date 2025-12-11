import logging
from typing import Any

from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import (  # ATTR_VARIABLES from script.const has import issues
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_VARIABLES,
)

from custom_components.supernotify import (
    ATTR_DATA,
    ATTR_PRIORITY,
    OPTION_CHIME_ALIASES,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    RE_DEVICE_ID,
    TRANSPORT_CHIME,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target, TargetRequired, TransportConfig
from custom_components.supernotify.transport import Transport

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
DEVICE_MODEL_EXCLUDE = ["Speaker Group"]


class ChimeTargetConfig:
    def __init__(
        self,
        entity_id: str | None = None,
        device_id: str | None = None,
        tune: str | None = None,
        duration: int | None = None,
        volume: float | None = None,
        data: dict[str, Any] | None = None,
        domain: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.entity_id: str | None = entity_id
        self.device_id: str | None = device_id
        self.domain: str | None = None
        self.entity_name: str | None = None
        if self.entity_id:
            self.domain, self.entity_name = self.entity_id.split(".", 1)
        elif self.device_id:
            self.domain = domain
        else:
            raise ValueError("ChimeTargetConfig target must be entity_id or device_id")
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


class ChimeTransport(Transport):
    name = TRANSPORT_CHIME

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.options = {}
        config.delivery_defaults.target_required = TargetRequired.OPTIONAL
        config.device_domain = DEVICE_DOMAINS
        config.device_model_exclude = DEVICE_MODEL_EXCLUDE
        config.delivery_defaults.options = {
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID, ATTR_DEVICE_ID],
            OPTION_TARGET_INCLUDE_RE: [RE_VALID_CHIME, RE_DEVICE_ID],
        }
        return config

    @property
    def chime_aliases(self) -> dict[str, Any]:
        return self.delivery_defaults.options.get(OPTION_CHIME_ALIASES) or {}

    def validate_action(self, action: str | None) -> bool:
        return action is None

    async def deliver(self, envelope: Envelope) -> bool:
        data: dict[str, Any] = {}
        data.update(envelope.delivery.data)
        data.update(envelope.data or {})
        target: Target = envelope.target

        # chime_repeat = data.pop("chime_repeat", 1)
        chime_tune: str | None = data.pop("chime_tune", None)
        chime_volume: float | None = data.pop("chime_volume", None)
        chime_duration: int | None = data.pop("chime_duration", None)

        _LOGGER.info(
            "SUPERNOTIFY notify_chime: %s -> %s (delivery: %s, env_data:%s, dlv_data:%s)",
            chime_tune,
            target.entity_ids,
            envelope.delivery_name,
            envelope.data,
            envelope.delivery.data,
        )
        # expand groups
        expanded_targets = {
            e: ChimeTargetConfig(tune=chime_tune, volume=chime_volume, duration=chime_duration, entity_id=e)
            for e in self.hass_api.expand_group(target.entity_ids)
        }
        expanded_targets.update({
            d: ChimeTargetConfig(tune=chime_tune, volume=chime_volume, duration=chime_duration, device_id=d)
            for d in target.device_ids
        })
        # resolve and include chime aliases
        expanded_targets.update(self.resolve_tune(chime_tune))  # overwrite and extend

        chimes = 0
        if not expanded_targets:
            _LOGGER.info("SUPERNOTIFY skipping chime, no targets")
            return False
        for chime_entity_config in expanded_targets.values():
            _LOGGER.debug("SUPERNOTIFY chime %s: %s", chime_entity_config.entity_id, chime_entity_config.tune)
            action_data = None
            try:
                domain, service, action_data, target_data = self.analyze_target(chime_entity_config, data, envelope)
                if domain is not None and service is not None:
                    action_data = self.prune_data(domain, action_data)

                    if await self.call_action(
                        envelope, qualified_action=f"{domain}.{service}", action_data=action_data, target_data=target_data
                    ):
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
    ) -> tuple[str | None, str | None, dict[str, Any], dict[str, Any]]:

        if not target_config.entity_id and not target_config.device_id:
            _LOGGER.warning("SUPERNOTIFY Empty chime target")
            return "", None, {}, {}

        domain: str | None = None
        name: str | None = None

        # Alexa Devices use device_id not entity_id for sounds
        # TODO: use method or delivery config vs fixed local constant for domains
        if target_config.device_id is not None and DEVICE_DOMAINS:
            if target_config.domain is not None and target_config.domain in DEVICE_DOMAINS:
                _LOGGER.debug(f"SUPERNOTIFY Chime selected target {domain} for {target_config.domain}")
                domain = target_config.domain
            else:
                domain = self.hass_api.domain_for_device(target_config.device_id, DEVICE_DOMAINS)
                _LOGGER.debug(f"SUPERNOTIFY Chime selected device {domain} for {target_config.device_id}")

        elif target_config.entity_id and "." in target_config.entity_id:
            domain, name = target_config.entity_id.split(".", 1)

        action_data: dict[str, Any] = {}
        target_data: dict[str, Any] = {}
        action: str | None = None

        if domain == "switch":
            action = "turn_on"
            target_data[ATTR_ENTITY_ID] = target_config.entity_id

        elif domain == "siren":
            action = "turn_on"
            target_data[ATTR_ENTITY_ID] = target_config.entity_id
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
            target_data[ATTR_ENTITY_ID] = target_config.entity_id
            action_data["media_content_type"] = "sound"
            action_data["media_content_id"] = target_config.tune

        else:
            _LOGGER.warning(
                "SUPERNOTIFY No matching chime domain/tune: %s, target: %s, tune: %s",
                domain,
                target_config.entity_id,
                target_config.tune,
            )

        _LOGGER.debug(
            "SUPERNOTIFY analyze_chime->%s.%s,action data: %s, target_data: %s", domain, action, action_data, target_data
        )

        return domain, action, action_data, target_data

    def resolve_tune(self, tune_or_alias: str | None) -> dict[str, ChimeTargetConfig]:
        target_configs: dict[str, ChimeTargetConfig] = {}
        if tune_or_alias is not None:
            for label, alias_config in self.chime_aliases.get(tune_or_alias, {}).items():
                if isinstance(alias_config, str):
                    tune = alias_config
                    alias_config = {}
                else:
                    tune = alias_config.get("tune", tune_or_alias)

                alias_config["tune"] = tune
                alias_config.setdefault("domain", label)
                alias_config.setdefault("data", {})
                raw_target = alias_config.pop("target", None)

                # pass through variables or data if present
                if raw_target is not None:
                    target = Target(raw_target)
                    target_configs.update({t: ChimeTargetConfig(entity_id=t, **alias_config) for t in target.entity_ids})
                    target_configs.update({t: ChimeTargetConfig(device_id=t, **alias_config) for t in target.device_ids})
                elif alias_config["domain"] in DEVICE_DOMAINS:
                    # bulk apply to all known target devices of this domain
                    bulk_apply = {
                        dev: ChimeTargetConfig(device_id=dev, **alias_config)
                        for dev in self.targets.device_ids
                        if dev not in target_configs  # don't overwrite existing specific targets
                        and ATTR_DEVICE_ID not in alias_config
                    }
                    # TODO: Constrain to device domain
                    target_configs.update(bulk_apply)
                else:
                    # bulk apply to all known target entities of this domain
                    bulk_apply = {
                        ent: ChimeTargetConfig(entity_id=ent, **alias_config)
                        for ent in self.targets.entity_ids
                        if ent.startswith(f"{alias_config['domain']}.")
                        and ent not in target_configs  # don't overwrite existing specific targets
                        and ATTR_ENTITY_ID not in alias_config
                    }
                    target_configs.update(bulk_apply)
        _LOGGER.debug("SUPERNOTIFY transport_chime: Resolved tune %s to %s", tune_or_alias, target_configs)
        return target_configs
