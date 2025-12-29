import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol
from homeassistant.components.notify.const import ATTR_MESSAGE, ATTR_TITLE
from homeassistant.const import (  # ATTR_VARIABLES from script.const has import issues
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DOMAIN,
    CONF_TARGET,
)
from homeassistant.exceptions import NoEntitySpecifiedError
from homeassistant.helpers.typing import ConfigType
from voluptuous.humanize import humanize_error

from custom_components.supernotify import (
    ATTR_DATA,
    ATTR_MEDIA,
    ATTR_PRIORITY,
    CHIME_ALIASES_SCHEMA,
    CONF_TUNE,
    OPTION_CHIME_ALIASES,
    OPTION_TARGET_CATEGORIES,
    OPTION_TARGET_INCLUDE_RE,
    OPTIONS_CHIME_DOMAINS,
    RE_DEVICE_ID,
    TRANSPORT_CHIME,
)
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import DebugTrace, Target, TargetRequired, TransportConfig, TransportFeature
from custom_components.supernotify.transport import Transport

RE_VALID_CHIME = r"(switch|script|group|rest_command|siren|media_player)\.[A-Za-z0-9_]+"

_LOGGER = logging.getLogger(__name__)

DEVICE_DOMAINS = ["alexa_devices"]
DEVICE_MODEL_EXCLUDE = ["Speaker Group"]


@dataclass
class ActionCall:
    domain: str
    service: str
    action_data: dict[str, Any] | None = field(default_factory=dict)
    target_data: dict[str, Any] | None = field(default_factory=dict)


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
        if self.entity_id and "." in self.entity_id:
            self.domain, self.entity_name = self.entity_id.split(".", 1)
        elif self.device_id:
            self.domain = domain
        else:
            _LOGGER.warning(
                "SUPERNOTIFY Invalid chime target, entity_id: %s, device_id %s, tune:%s", entity_id, device_id, tune
            )
            raise NoEntitySpecifiedError("ChimeTargetConfig target must be entity_id or device_id")
        if kwargs:
            _LOGGER.warning("SUPERNOTIFY ChimeTargetConfig ignoring unexpected args: %s", kwargs)
        self.volume: float | None = volume
        self.tune: str | None = tune
        self.duration: int | None = duration
        self.data: dict[str, Any] | None = data or {}

    def as_dict(self, **kwargs) -> dict[str, Any]:  # noqa: ARG002
        return {
            "entity_id": self.entity_id,
            "device_id": self.device_id,
            "domain": self.domain,
            "tune": self.tune,
            "duration": self.duration,
            "volume": self.volume,
            "data": self.data,
        }

    def __repr__(self) -> str:
        """Return a developer-oriented string representation of this ChimeTargetConfig"""
        if self.device_id is not None:
            return f"ChimeTargetConfig(device_id={self.device_id})"
        return f"ChimeTargetConfig(entity_id={self.entity_id})"


class MiniChimeTransport:
    domain: str

    @abstractmethod
    def build(
        self,
        target_config: ChimeTargetConfig,
        action_data: dict[str, Any],
        entity_name: str | None = None,
        envelope: Envelope | None = None,
        **_kwargs: Any,
    ) -> ActionCall | None:
        raise NotImplementedError()


class RestCommandChimeTransport(MiniChimeTransport):
    domain = "rest_command"

    def build(  # type: ignore[override]
        self, target_config: ChimeTargetConfig, entity_name: str | None, **_kwargs: Any
    ) -> ActionCall | None:
        if entity_name is None:
            _LOGGER.warning("SUPERNOTIFY rest_command chime target requires entity")
            return None
        output_data = target_config.data or {}
        if target_config.data:
            output_data.update(target_config.data)
        return ActionCall(self.domain, entity_name, action_data=output_data)


class SwitchChimeTransport(MiniChimeTransport):
    domain = "switch"

    def build(self, target_config: ChimeTargetConfig, **_kwargs: Any) -> ActionCall | None:  # type: ignore[override]
        return ActionCall(self.domain, "turn_on", target_data={ATTR_ENTITY_ID: target_config.entity_id})


class SirenChimeTransport(MiniChimeTransport):
    domain = "siren"

    def build(self, target_config: ChimeTargetConfig, **_kwargs: Any) -> ActionCall | None:  # type: ignore[override]
        output_data: dict[str, Any] = {ATTR_DATA: {}}
        if target_config.tune:
            output_data[ATTR_DATA]["tone"] = target_config.tune
        if target_config.duration is not None:
            output_data[ATTR_DATA]["duration"] = target_config.duration
        if target_config.volume is not None:
            output_data[ATTR_DATA]["volume_level"] = target_config.volume
        return ActionCall(
            self.domain, "turn_on", action_data=output_data, target_data={ATTR_ENTITY_ID: target_config.entity_id}
        )


class ScriptChimeTransport(MiniChimeTransport):
    domain = "script"

    def build(  # type: ignore[override]
        self,
        target_config: ChimeTargetConfig,
        entity_name: str | None,
        envelope: Envelope,
        **_kwargs: Any,
    ) -> ActionCall | None:
        if entity_name is None:
            _LOGGER.warning("SUPERNOTIFY script chime target requires entity")
            return None
        variables: dict[str, Any] = target_config.data or {}
        variables[ATTR_MESSAGE] = envelope.message
        variables[ATTR_TITLE] = envelope.title
        variables[ATTR_PRIORITY] = envelope.priority
        variables["chime_tune"] = target_config.tune
        variables["chime_volume"] = target_config.volume
        variables["chime_duration"] = target_config.duration
        output_data: dict[str, Any] = {"variables": variables}
        if envelope.delivery.debug:
            output_data["wait"] = envelope.delivery.debug
        # use `turn_on` rather than direct call to run script in background
        return ActionCall(
            self.domain, "turn_on", action_data=output_data, target_data={ATTR_ENTITY_ID: target_config.entity_id}
        )


class AlexaDevicesChimeTransport(MiniChimeTransport):
    domain = "alexa_devices"

    def build(self, target_config: ChimeTargetConfig, **_kwargs: Any) -> ActionCall | None:  # type: ignore[override]
        output_data: dict[str, Any] = {
            "device_id": target_config.device_id,
            "sound": target_config.tune,
        }
        return ActionCall(self.domain, "send_sound", action_data=output_data)


class MediaPlayerChimeTransport(MiniChimeTransport):
    domain = "media_player"

    def build(self, target_config: ChimeTargetConfig, action_data: dict[str, Any], **_kwargs: Any) -> ActionCall | None:  # type: ignore[override]
        input_data = target_config.data or {}
        if action_data:
            input_data.update(action_data)
        output_data: dict[str, Any] = {
            "media": {
                "media_content_type": input_data.get(ATTR_MEDIA, {"media_content_type": "sound"}).get(
                    "media_content_type", "sound"
                ),
                "media_content_id": target_config.tune,
            }
        }
        if input_data.get("enqueue") is not None:
            output_data["enqueue"] = input_data.get("enqueue")
        if input_data.get("announce") is not None:
            output_data["announce"] = input_data.get("announce")

        return ActionCall(
            self.domain, "play_media", action_data=output_data, target_data={ATTR_ENTITY_ID: target_config.entity_id}
        )


class ChimeTransport(Transport):
    name = TRANSPORT_CHIME

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # FIXME: handle chime aliases in delivery so config can be broken up or overridden in delivery data  # noqa: TD001
        if OPTION_CHIME_ALIASES in self.delivery_defaults.options:
            self.chime_aliases: ConfigType = self.build_aliases(self.delivery_defaults.options[OPTION_CHIME_ALIASES])
            if self.chime_aliases:
                _LOGGER.info("SUPERNOTIFY Set up %s chime aliases", len(self.chime_aliases))
            else:
                _LOGGER.warning("SUPERNOTIFY Chime aliases configured but not recognized")
        else:
            self.chime_aliases = {}
            _LOGGER.debug("SUPERNOTIFY No chime aliases configures")
        self.mini_transports: dict[str, MiniChimeTransport] = {
            t.domain: t
            for t in [
                RestCommandChimeTransport(),
                SwitchChimeTransport(),
                SirenChimeTransport(),
                ScriptChimeTransport(),
                AlexaDevicesChimeTransport(),
                MediaPlayerChimeTransport(),
            ]
        }

    @property
    def supported_features(self) -> TransportFeature:
        return TransportFeature(0)

    def build_aliases(self, src_config: ConfigType) -> ConfigType:
        dest_config: dict[str, Any] = {}
        try:
            validated: ConfigType = CHIME_ALIASES_SCHEMA({OPTION_CHIME_ALIASES: src_config})
            for alias, alias_config in validated[OPTION_CHIME_ALIASES].items():
                alias_config = alias_config or {}
                for domain_or_label, domain_config in alias_config.items():
                    domain_config = domain_config or {}
                    if isinstance(domain_config, str):
                        domain_config = {CONF_TUNE: domain_config}
                    domain_config.setdefault(CONF_TUNE, alias)
                    if domain_or_label in OPTIONS_CHIME_DOMAINS:
                        domain_config.setdefault(CONF_DOMAIN, domain_or_label)

                    try:
                        if domain_config.get(CONF_TARGET):
                            domain_config[CONF_TARGET] = Target(domain_config[CONF_TARGET])
                            if not domain_config[CONF_TARGET].has_targets():
                                _LOGGER.warning("SUPERNOTIFY chime alias %s has empty target", alias)
                            elif domain_config[CONF_TARGET].has_unknown_targets():
                                _LOGGER.warning("SUPERNOTIFY chime alias %s has unknown targets", alias)
                        dest_config.setdefault(alias, {})
                        dest_config[alias][domain_or_label] = domain_config
                    except Exception as e:
                        _LOGGER.exception("SUPERNOTIFY chime alias %s has invalid target: %s", alias, e)

        except vol.Invalid as ve:
            _LOGGER.error("SUPERNOTIFY Chime alias configuration error: %s", ve)
            _LOGGER.error("SUPERNOTIFY %s", humanize_error(src_config, ve))
        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Chime alias unexpected error: %s", e)
        return dest_config

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.options = {}
        config.device_discovery = True
        config.delivery_defaults.target_required = TargetRequired.OPTIONAL
        config.device_domain = DEVICE_DOMAINS
        config.device_model_exclude = DEVICE_MODEL_EXCLUDE
        config.delivery_defaults.options = {
            OPTION_TARGET_CATEGORIES: [ATTR_ENTITY_ID, ATTR_DEVICE_ID],
            OPTION_TARGET_INCLUDE_RE: [RE_VALID_CHIME, RE_DEVICE_ID],
        }
        return config

    def validate_action(self, action: str | None) -> bool:
        return action is None

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        data: dict[str, Any] = {}
        data.update(envelope.delivery.data)
        data.update(envelope.data or {})
        target: Target = envelope.target

        # chime_repeat = data.pop("chime_repeat", 1)
        chime_tune: str | None = data.pop("chime_tune", None)
        chime_volume: float | None = data.pop("chime_volume", None)
        chime_duration: int | None = data.pop("chime_duration", None)

        _LOGGER.debug(
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
        if debug_trace:
            debug_trace.record_delivery_artefact(envelope.delivery.name, "expanded_targets", expanded_targets)

        for chime_entity_config in expanded_targets.values():
            _LOGGER.debug("SUPERNOTIFY chime %s: %s", chime_entity_config.entity_id, chime_entity_config.tune)
            action_data: dict[str, Any] | None = None
            try:
                action_call: ActionCall | None = self.analyze_target(chime_entity_config, data, envelope)
                if action_call is not None:
                    if await self.call_action(
                        envelope,
                        qualified_action=f"{action_call.domain}.{action_call.service}",
                        action_data=action_call.action_data,
                        target_data=action_call.target_data,
                    ):
                        chimes += 1
                else:
                    _LOGGER.debug("SUPERNOTIFY Chime skipping incomplete service for %s", chime_entity_config.entity_id)
            except Exception:
                _LOGGER.exception("SUPERNOTIFY Failed to chime %s: %s [%s]", chime_entity_config.entity_id, action_data)
        return chimes > 0

    def analyze_target(self, target_config: ChimeTargetConfig, data: dict[str, Any], envelope: Envelope) -> ActionCall | None:

        if not target_config.entity_id and not target_config.device_id:
            _LOGGER.warning("SUPERNOTIFY Empty chime target")
            return None

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
        if not domain:
            _LOGGER.warning("SUPERNOTIFY Unknown domain: %s", target_config)
            return None
        mini_transport: MiniChimeTransport | None = self.mini_transports.get(domain)
        if mini_transport is None:
            _LOGGER.warning(
                "SUPERNOTIFY No matching chime domain/tune: %s, target: %s, tune: %s",
                domain,
                target_config.entity_id,
                target_config.tune,
            )
            return None

        action_call: ActionCall | None = mini_transport.build(
            envelope=envelope, entity_name=name, action_data=data, target_config=target_config
        )
        _LOGGER.debug("SUPERNOTIFY analyze_chime->%s", action_call)

        return action_call

    def resolve_tune(self, tune_or_alias: str | None) -> dict[str, ChimeTargetConfig]:
        target_configs: dict[str, ChimeTargetConfig] = {}
        if tune_or_alias is not None:
            for alias_config in self.chime_aliases.get(tune_or_alias, {}).values():
                target = alias_config.get(CONF_TARGET, None)
                # pass through variables or data if present
                if target is not None:
                    target_configs.update({t: ChimeTargetConfig(entity_id=t, **alias_config) for t in target.entity_ids})
                    target_configs.update({t: ChimeTargetConfig(device_id=t, **alias_config) for t in target.device_ids})
                elif alias_config[CONF_DOMAIN] in DEVICE_DOMAINS:
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
                        if ent.startswith(f"{alias_config[CONF_DOMAIN]}.")
                        and ent not in target_configs  # don't overwrite existing specific targets
                        and ATTR_ENTITY_ID not in alias_config
                    }
                    target_configs.update(bulk_apply)
        _LOGGER.debug("SUPERNOTIFY transport_chime: Resolved tune %s to %s", tune_or_alias, target_configs)
        return target_configs
