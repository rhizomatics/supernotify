# mypy: disable-error-code="name-defined"

import logging
import time
from abc import abstractmethod
from dataclasses import asdict
from traceback import format_exception
from typing import Any
from urllib.parse import urlparse

from homeassistant.components.notify.const import ATTR_TARGET
from homeassistant.const import CONF_ACTION, CONF_CONDITION, CONF_DEFAULT, CONF_METHOD, CONF_NAME, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import condition

from custom_components.supernotify.common import CallRecord
from custom_components.supernotify.configuration import Context

from . import (
    CONF_DATA,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_TARGETS_REQUIRED,
    RESERVED_DELIVERY_NAMES,
    ConditionVariables,
    MessageOnlyPolicy,
)

_LOGGER = logging.getLogger(__name__)

OPTION_SIMPLIFY_TEXT = "simplify_text"
OPTION_STRIP_URLS = "strip_urls"
OPTION_MESSAGE_USAGE = "message_usage"
OPTIONS_WITH_DEFAULTS: dict[str, str | bool] = {
    OPTION_SIMPLIFY_TEXT: False,
    OPTION_STRIP_URLS: False,
    OPTION_MESSAGE_USAGE: MessageOnlyPolicy.STANDARD,
}


class DeliveryMethod:
    """Base class for delivery methods.

    Sub classes integrste with Home Assistant notification services
    or alternative notification mechanisms.
    """

    method: str

    @abstractmethod
    def __init__(
        self,
        hass: HomeAssistant,
        context: Context,
        deliveries: dict[str, Any] | None = None,
        default: dict[str, Any] | None = None,
        targets_required: bool = True,
        device_domain: list[str] | None = None,
        device_discovery: bool = False,
    ) -> None:
        self.hass: HomeAssistant = hass
        self.context: Context = context
        self.default: dict[str, Any] = default or {}
        self.default_options: dict[str, Any] = self.default.get(CONF_OPTIONS) or {}
        self.default_action: str | None = self.default.get(CONF_ACTION)
        self.targets_required: bool = targets_required
        self.device_domain: list[str] = device_domain or []
        self.device_discovery: bool = device_discovery

        self.default_delivery: dict[str, Any] | None = None
        self.valid_deliveries: dict[str, dict[str, Any]] = {}
        self.method_deliveries: dict[str, dict[str, Any]] = (
            {d: dc for d, dc in deliveries.items() if dc.get(CONF_METHOD) == self.method} if deliveries else {}
        )

    async def initialize(self) -> None:
        """Async post-construction initialization"""
        if self.method is None:
            raise ValueError("No delivery method configured")
        self.valid_deliveries = await self.validate_deliveries()
        if self.device_discovery:
            self.default.setdefault(CONF_TARGET, [])
            for domain in self.device_domain:
                discovered: int = 0
                added: int = 0
                for d in self.context.discover_devices(domain):
                    discovered += 1
                    if d.id not in self.default[CONF_TARGET]:
                        _LOGGER.info(f"SUPERNOTIFY Discovered device {d.name} for {domain}, id {d.id}")
                        self.default[CONF_TARGET].append(d.id)
                        added += 1

                _LOGGER.info(f"SUPERNOTIFY device discovery for {domain} found {discovered} devices, added {added} new ones")

    @property
    def targets(self) -> list[str]:
        return self.default.get(CONF_TARGET) or []

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if delivery method has fixed action or doesn't require one"""
        return action is None or action.startswith("notify.")

    async def validate_deliveries(self) -> dict[str, dict[str, Any]]:
        """Validate list of deliveries at startup for this method"""
        valid_deliveries: dict[str, dict[str, Any]] = {}
        for d, dc in self.method_deliveries.items():
            # don't care about ENABLED here since disabled deliveries can be overridden
            if d in RESERVED_DELIVERY_NAMES:
                _LOGGER.warning("SUPERNOTIFY Delivery uses reserved word %s", d)
                self.context.raise_issue(f"method_{self.method}_reserved_delivery_name",
                        issue_key="method_reserved_delivery_name",
                        issue_map={"method": self.method, "delivery": d})
                continue
            if not self.validate_action(dc.get(CONF_ACTION)):
                _LOGGER.warning("SUPERNOTIFY Invalid action definition for delivery %s (%s)", d, dc.get(CONF_ACTION))
                self.context.raise_issue(f"method_{self.method}_invalid_delivery_action",
                        issue_key="method_invalid_delivery_action",
                        issue_map={"method": self.method, "delivery": d, "action": str(dc.get(CONF_ACTION))})
                continue
            delivery_condition = dc.get(CONF_CONDITION)
            if delivery_condition:
                if not await condition.async_validate_condition_config(self.hass, delivery_condition):
                    _LOGGER.warning("SUPERNOTIFY Invalid delivery condition for %s: %s", d, delivery_condition)
                    self.context.raise_issue(f"method_{self.method}_invalid_delivery_condition",
                        issue_key="method_invalid_delivery_condition",
                        issue_map={"method": self.method, "delivery": d, "condition": delivery_condition})
                    continue

            valid_deliveries[d] = dc
            dc[CONF_NAME] = d

            if dc.get(CONF_DEFAULT) and not self.default_delivery:
                # pick the first delivery with default flag set as the default
                self.default_delivery = dc
            elif dc.get(CONF_DEFAULT) and self.default_delivery and dc.get(CONF_NAME) != self.default_delivery.get(CONF_NAME):
                _LOGGER.debug("SUPERNOTIFY Multiple default deliveries, skipping %s", d)

        if not self.default_delivery:
            method_definition = self.default
            if method_definition:
                _LOGGER.info("SUPERNOTIFY Building default delivery for %s from method %s", self.method, method_definition)
                self.default_delivery = method_definition
            else:
                _LOGGER.debug("SUPERNOTIFY No default delivery or method_definition for method %s", self.method)

        if self.default_action is None and self.default_delivery:
            self.default_action = self.default_delivery.get(CONF_ACTION)
            _LOGGER.debug("SUPERNOTIFY Setting default action for method %s to %s", self.method, self.default_action)
        else:
            _LOGGER.debug("SUPERNOTIFY No default action for method %s", self.method)

        _LOGGER.debug(
            "SUPERNOTIFY Validated method %s, default delivery %s, default action %s, valid deliveries: %s",
            self.method,
            self.default_delivery,
            self.default_action,
            valid_deliveries,
        )
        return valid_deliveries

    def attributes(self) -> dict[str, Any]:
        return {
            CONF_METHOD: self.method,
            CONF_TARGETS_REQUIRED: self.targets_required,
            CONF_DEVICE_DOMAIN: self.device_domain,
            CONF_DEVICE_DISCOVERY: self.device_discovery,
            CONF_DEFAULT: self.default,
            "default_delivery": self.default_delivery,
            "deliveries": list(self.valid_deliveries.keys()),
        }

    @abstractmethod
    async def deliver(self, envelope: "Envelope") -> bool:  # noqa: F821 # type: ignore
        """Delivery implementation

        Args:
        ----
            envelope (Envelope): envelope to be delivered

        """

    def select_target(self, target: str) -> bool:  # noqa: ARG002
        """Confirm if target appropriate for this delivery method

        Args:
        ----
            target (str): Target, typically an entity ID, or an email address, phone number

        """
        return True

    def recipient_target(self, recipient: dict[str, Any]) -> list[str]:  # noqa: ARG002
        """Pick out delivery appropriate target from a single person's (recipient) config"""
        return []

    def delivery_config(self, delivery_name: str) -> dict[str, Any]:
        config = self.context.deliveries.get(delivery_name) or self.default_delivery or {}
        config = dict(config)
        config[CONF_DATA] = dict(config.get(CONF_DATA) or {})
        return config

    def set_action_data(self, action_data: dict[str, Any], key: str, data: Any | None) -> Any:
        if data is not None:
            action_data[key] = data
        return action_data

    def option(self, option_name: str, delivery_config: dict[str, Any]) -> str | bool:
        """Get an option value from delivery config or method default options"""
        opt: str | bool | None = None
        if CONF_OPTIONS in delivery_config and option_name in delivery_config[CONF_OPTIONS]:
            opt = delivery_config[CONF_OPTIONS][option_name]
        if opt is None:
            opt = self.default_options.get(option_name)
        if opt is None:
            opt = OPTIONS_WITH_DEFAULTS.get(option_name)
        if opt is None:
            _LOGGER.warning("SUPERNOTIFY No default for option %s, setting to empty string", option_name)
            opt = ""
        return opt

    def option_bool(self, option_name: str, delivery_config: dict[str, Any]) -> bool:
        return bool(self.option(option_name, delivery_config))

    def option_str(self, option_name: str, delivery_config: dict[str, Any]) -> str:
        return str(self.option(option_name, delivery_config))

    async def evaluate_delivery_conditions(
        self, delivery_config: dict[str, Any], condition_variables: ConditionVariables | None
    ) -> bool | None:
        if CONF_CONDITION not in delivery_config:
            return True
        cond_conf = delivery_config.get(CONF_CONDITION)
        if cond_conf is None:
            return True

        try:
            test = await condition.async_from_config(self.hass, cond_conf)
            return test(self.hass, asdict(condition_variables) if condition_variables else None)
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Condition eval failed: %s", e)
            raise

    async def call_action(
        self,
        envelope: "Envelope",  # noqa: F821 # type: ignore
        qualified_action: str | None = None,
        action_data: dict[str, Any] | None = None,
        target_data: dict[str, Any] | None = None,
    ) -> bool:
        action_data = action_data or {}
        start_time = time.time()
        domain = service = None
        config = self.delivery_config(envelope.delivery_name)
        try:
            qualified_action = qualified_action or config.get(CONF_ACTION) or self.default_action
            targets_required: bool = config.get(CONF_TARGETS_REQUIRED, self.targets_required)
            if qualified_action and (action_data.get(ATTR_TARGET) or not targets_required or target_data):
                domain, service = qualified_action.split(".", 1)
                start_time = time.time()
                envelope.calls.append(CallRecord(time.time() - start_time, domain, service, action_data, target_data))
                if target_data:
                    await self.hass.services.async_call(domain, service, service_data=action_data, target=target_data)
                else:
                    await self.hass.services.async_call(domain, service, service_data=action_data)
                envelope.delivered = 1
            else:
                _LOGGER.debug(
                    "SUPERNOTIFY skipping action call for service %s, targets %s",
                    qualified_action,
                    action_data.get(ATTR_TARGET),
                )
                envelope.skipped = 1
            return True
        except Exception as e:
            envelope.failed_calls.append(
                CallRecord(time.time() - start_time, domain, service, action_data, target_data, exception=str(e))
            )
            _LOGGER.error("SUPERNOTIFY Failed to notify %s via %s, data=%s : %s", self.method, qualified_action, action_data, e)
            envelope.errored += 1
            envelope.delivery_error = format_exception(e)
            return False

    def abs_url(self, fragment: str | None, prefer_external: bool = True) -> str | None:
        base_url = self.context.hass_external_url if prefer_external else self.context.hass_internal_url
        if fragment:
            if fragment.startswith("http"):
                return fragment
            if fragment.startswith("/"):
                return base_url + fragment
            return base_url + "/" + fragment
        return None

    def simplify(self, text: str | None, strip_urls: bool = False) -> str | None:
        """Simplify text for delivery methods with speaking or plain text interfaces"""
        if not text:
            return None
        if strip_urls:
            words = text.split()
            text = " ".join(word for word in words if not urlparse(word).scheme)
        text = text.translate(str.maketrans("_", " ", "()£$<>"))
        _LOGGER.debug("SUPERNOTIFY Simplified text to: %s", text)
        return text
