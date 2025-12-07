from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType
from typing import cast

import homeassistant.components.trace
from homeassistant.components.trace.const import DATA_TRACE
from homeassistant.components.trace.models import ActionTrace
from homeassistant.components.trace.util import async_store_trace
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConditionError, ConditionErrorContainer
from homeassistant.helpers import condition as condition
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType
import socket
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING

from homeassistant.components import mqtt
from homeassistant.components.group import expand_entity_ids

# type: ignore[attr-defined,unused-ignore]
from homeassistant.core import Context as HomeAssistantContext
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.trace import trace_get, trace_path
from homeassistant.helpers.typing import ConfigType

from .model import ConditionVariables

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import ServiceResponse, State

from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.network import get_url

from . import DOMAIN, ConditionsFunc

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
    from homeassistant.helpers.typing import ConfigType


_LOGGER = logging.getLogger(__name__)


class HomeAssistantAPI:
    def __init__(self, hass: HomeAssistant | None = None) -> None:
        self._hass = hass
        self.internal_url: str = ""
        self.external_url: str = ""
        self.hass_name: str = "!UNDEFINED!"
        self._entity_registry: entity_registry.EntityRegistry | None = None
        self._device_registry: device_registry.DeviceRegistry | None = None
        self._service_info: dict[tuple[str, str], Any] = {}

    def initialize(self) -> None:
        if self._hass:
            self.hass_name = self._hass.config.location_name
            try:
                self.internal_url = get_url(self._hass, prefer_external=False)
            except Exception as e:
                self.internal_url = f"http://{socket.gethostname()}"
                _LOGGER.warning("SUPERNOTIFY could not get internal hass url, defaulting to %s: %s", self.internal_url, e)
            try:
                self.external_url = get_url(self._hass, prefer_external=True)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY could not get external hass url, defaulting to internal url: %s", e)
                self.external_url = self.internal_url
        else:
            _LOGGER.warning("SUPERNOTIFY Configured without HomeAssistant instance")

        _LOGGER.debug(
            "SUPERNOTIFY Configured for HomeAssistant instance %s at %s , %s",
            self.hass_name,
            self.internal_url,
            self.external_url,
        )

        if not self.internal_url or not self.internal_url.startswith("http"):
            _LOGGER.warning("SUPERNOTIFY invalid internal hass url %s", self.internal_url)

    def in_hass_loop(self) -> bool:
        return self._hass is not None and self._hass.loop_thread_id == threading.get_ident()

    def get_state(self, entity_id: str) -> State | None:
        if not self._hass:
            return None
        return self._hass.states.get(entity_id)

    def set_state(self, entity_id: str, state: str) -> None:
        if not self._hass:
            return
        if self.in_hass_loop():
            self._hass.states.async_set(entity_id, state)
        else:
            self._hass.states.set(entity_id, state)

    def has_service(self, domain: str, service: str) -> bool:
        if not self._hass:
            return False
        return self._hass.services.has_service(domain, service)

    def entity_ids_for_domain(self, domain: str) -> list[str]:
        if self._hass:
            return self._hass.states.async_entity_ids(domain)
        return []

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        target_data: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> ServiceResponse | None:
        if not self._hass:
            raise ValueError("HomeAssistant not available")
        return_response: bool = debug
        blocking: bool = debug
        try:
            if (domain, service) not in self._service_info:
                service_objs = self._hass.services.async_services()
                service_obj = service_objs.get(domain, {}).get(service, {})
                self._service_info[domain, service] = {
                    "supports_response": service_obj.supports_response,
                    "schema": service_obj.schema,
                }
            service_info = self._service_info.get((domain, service), {})
            supports_response = service_info.get("supports_response")
            if supports_response is not None:
                if supports_response == SupportsResponse.NONE:
                    return_response = False
                elif supports_response == SupportsResponse.ONLY:
                    return_response = True
            else:
                _LOGGER.debug("SUPERNOTIFY Unable to find service info for %s.%s", domain, service)

        except Exception as e:
            _LOGGER.warning("SUPERNOTIFY Unable to get service info for %s.%s: %s", domain, service, e)

        response: ServiceResponse | None = await self._hass.services.async_call(
            domain,
            service,
            service_data=service_data,
            blocking=blocking,
            context=None,
            target=target_data,
            return_response=return_response,
        )
        if response is not None and debug:
            _LOGGER.info("SUPERNOTIFY Service %s.%s response: %s", domain, service, response)
        return response

    def expand_group(self, entity_ids: str | list[str]) -> list[str]:
        if self._hass is None:
            return []
        return expand_entity_ids(self._hass, entity_ids)

    def template(self, template_format: str) -> Template:
        return Template(template_format, self._hass)

    async def trace_conditions(
        self,
        conditions: ConditionsFunc,
        condition_variables: ConditionVariables,
        trace_name: str | None = None,
    ) -> tuple[bool | None, ActionTrace | None]:

        result: bool | None = None
        this_trace: ActionTrace | None = None
        if self._hass:
            if DATA_TRACE not in self._hass.data:
                _LOGGER.warning("SUPERNOTIFY tracing not configured, attempting to set up")
                await homeassistant.components.trace.async_setup(self._hass, {})  # type: ignore
            with trace_action(self._hass, trace_name or "anon_condition") as cond_trace:
                cond_trace.set_trace(trace_get())
                this_trace = cond_trace
                with trace_path(["condition", "conditions"]) as _tp:
                    result = self.evaluate_conditions(conditions, condition_variables)
                _LOGGER.debug(cond_trace.as_dict())
        return result, this_trace

    async def build_conditions(
        self, condition_config: list[ConfigType], strict: bool = False, validate: bool = False, name: str = DOMAIN
    ) -> ConditionsFunc | None:
        if self._hass is None:
            raise ValueError("HomeAssistant not available")
        capturing_logger: ConditionErrorLoggingAdaptor = ConditionErrorLoggingAdaptor(_LOGGER)
        condition_variables: ConditionVariables = ConditionVariables()
        cond_list: list[ConfigType]
        try:
            if validate:
                cond_list = cast(
                    "list[ConfigType]", await condition.async_validate_conditions_config(self._hass, condition_config)
                )
            else:
                cond_list = condition_config
        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Conditions validation failed: %s", e)
            raise
        try:
            if strict:
                force_strict_template_mode(cond_list, undo=False)

            test: ConditionsFunc = await condition.async_conditions_from_config(
                self._hass, cond_list, cast("logging.Logger", capturing_logger), name
            )
            if test is None:
                raise ValueError(f"Invalid condition {condition_config}")
            test(condition_variables.as_dict())
            if strict and capturing_logger.condition_errors:
                for exception in capturing_logger.condition_errors:
                    _LOGGER.warning("SUPERNOTIFY Invalid condition %s:%s", condition_config, exception)
                raise capturing_logger.condition_errors[0]
            return test
        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Conditions eval failed: %s", e)
            raise
        finally:
            if strict:
                force_strict_template_mode(condition_config, undo=True)

    def evaluate_conditions(
        self,
        condition: ConditionsFunc,
        condition_variables: ConditionVariables,
    ) -> bool | None:
        if self._hass is None:
            raise ValueError("HomeAssistant not available")
        try:
            return condition(condition_variables.as_dict() if condition_variables else None)
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Condition eval failed: %s", e)
            raise

    def abs_url(self, fragment: str | None, prefer_external: bool = True) -> str | None:
        base_url = self.external_url if prefer_external else self.internal_url
        if fragment:
            if fragment.startswith("http"):
                return fragment
            if fragment.startswith("/"):
                return base_url + fragment
            return base_url + "/" + fragment
        return None

    def raise_issue(
        self,
        issue_id: str,
        issue_key: str,
        issue_map: dict[str, str],
        severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
        learn_more_url: str = "https://supernotify.rhizomatics.org.uk",
        is_fixable: bool = False,
    ) -> None:
        if not self._hass:
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            issue_id,
            translation_key=issue_key,
            translation_placeholders=issue_map,
            severity=severity,
            learn_more_url=learn_more_url,
            is_fixable=is_fixable,
        )

    def discover_devices(self, discover_domain: str) -> list[DeviceEntry]:
        devices: list[DeviceEntry] = []
        dev_reg: DeviceRegistry | None = self.device_registry()
        if dev_reg is None:
            _LOGGER.warning(f"SUPERNOTIFY Unable to discover devices for {discover_domain} - no device registry found")
            return []

        all_devs = enabled_devs = found_devs = 0
        for dev in dev_reg.devices.values():
            all_devs += 1
            if not dev.disabled:
                enabled_devs += 1
                for identifier in dev.identifiers:
                    if identifier and len(identifier) > 1 and identifier[0] == discover_domain:
                        _LOGGER.debug("SUPERNOTIFY discovered device %s for id %s", dev.name, identifier)
                        devices.append(dev)
                        found_devs += 1
                    elif identifier:
                        # HomeKit has triples for identifiers, other domains may behave similarly
                        _LOGGER.debug("SUPERNOTIFY Unexpected device %s id: %s", dev.name, identifier)
                    else:
                        _LOGGER.debug(  # type: ignore
                            "SUPERNOTIFY Unexpected device %s without id", dev.name
                        )
        _LOGGER.info(
            f"SUPERNOTIFY {discover_domain} device discovery, all={all_devs}, enabled={enabled_devs}, found={found_devs}"
        )
        return devices

    def domain_for_device(self, device_id: str, domains: list[str]) -> str | None:
        # discover domain from device registry
        verified_domain: str | None = None
        device_registry = self.device_registry()
        if device_registry:
            device: DeviceEntry | None = device_registry.async_get(device_id)
            if device:
                matching_domains = [d for d, _id in device.identifiers if d in domains]
                if matching_domains:
                    # TODO: limited to first domain found, unlikely to be more
                    return matching_domains[0]
            _LOGGER.warning(
                "SUPERNOTIFY A target that looks like a device_id can't be matched to supported integration: %s",
                device_id,
            )
        return verified_domain

    def entity_registry(self) -> entity_registry.EntityRegistry | None:
        """Hass entity registry is weird, every component ends up creating its own, with a store, subscribing
        to all entities, so do it once here
        """  # noqa: D205
        if self._entity_registry is not None:
            return self._entity_registry
        if self._hass:
            try:
                self._entity_registry = entity_registry.async_get(self._hass)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to get entity registry: %s", e)
        return self._entity_registry

    def device_registry(self) -> device_registry.DeviceRegistry | None:
        """Hass device registry is weird, every component ends up creating its own, with a store, subscribing
        to all devices, so do it once here
        """  # noqa: D205
        if self._device_registry is not None:
            return self._device_registry
        if self._hass:
            try:
                self._device_registry = device_registry.async_get(self._hass)
            except Exception as e:
                _LOGGER.warning("SUPERNOTIFY Unable to get device registry: %s", e)
        return self._device_registry

    async def mqtt_available(self, raise_on_error: bool = True) -> bool:
        if self._hass:
            try:
                return await mqtt.async_wait_for_mqtt_client(self._hass) is True
            except Exception:
                _LOGGER.exception("SUPERNOTIFY MQTT integration failed on available check")
                if raise_on_error:
                    raise
        return False

    async def mqtt_publish(
        self, topic: str, payload: Any = None, qos: int = 0, retain: bool = False, raise_on_error: bool = True
    ) -> None:
        if self._hass:
            try:
                await mqtt.async_publish(
                    self._hass,
                    topic=topic,
                    payload=json_dumps(payload),
                    qos=qos,
                    retain=retain,
                )
            except Exception:
                _LOGGER.exception(f"SUPERNOTIFY MQTT publish failed to {topic}")
                if raise_on_error:
                    raise


class ConditionErrorLoggingAdaptor(logging.LoggerAdapter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.condition_errors: list[ConditionError] = []

    def capture(self, args: Any) -> None:
        if args and isinstance(args, (list, tuple)):
            for arg in args:
                if isinstance(arg, ConditionErrorContainer):
                    self.condition_errors.extend(arg.errors)
                elif isinstance(arg, ConditionError):
                    self.condition_errors.append(arg)

    def error(self, msg: Any, *args: object, **kwargs: Any) -> None:
        self.capture(args)
        self.logger.error(msg, args, kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        self.capture(args)
        self.logger.warning(msg, args, kwargs)


def force_strict_template_mode(conditions: list[ConfigType], undo: bool = False) -> None:
    class TemplateWrapper:
        def __init__(self, obj: Template) -> None:
            self._obj = obj

        def __getattr__(self, name: str) -> Any:
            if name == "async_render_to_info":
                return partial(self._obj.async_render_to_info, strict=True)
            return getattr(self._obj, name)

        def __setattr__(self, name: str, value: Any) -> None:
            super().__setattr__(name, value)

    def wrap_template(cond: ConfigType, undo: bool) -> ConfigType:
        for key, val in cond.items():
            if not undo and isinstance(val, Template) and hasattr(val, "_env"):
                cond[key] = TemplateWrapper(val)
            elif undo and isinstance(val, TemplateWrapper):
                cond[key] = val._obj
            elif isinstance(val, dict):
                wrap_template(val, undo)
        return cond

    if conditions is not None:
        conditions = [wrap_template(condition, undo) for condition in conditions]


@contextmanager
def trace_action(
    hass: HomeAssistant,
    item_id: str,
    config: dict[str, Any] | None = None,
    context: HomeAssistantContext | None = None,
    stored_traces: int = 5,
) -> Iterator[ActionTrace]:
    """Trace execution of a condition"""
    trace = ActionTrace(item_id, config, None, context or HomeAssistantContext())
    async_store_trace(hass, trace, stored_traces)

    try:
        yield trace
    except Exception as ex:
        if item_id:
            trace.set_error(ex)
        raise
    finally:
        if item_id:
            trace.finished()
