# mypy: disable-error-code="name-defined"

import logging
import time
from abc import abstractmethod
from dataclasses import asdict
from traceback import format_exception
from typing import Any
from urllib.parse import urlparse

from homeassistant.components.notify.const import ATTR_TARGET
from homeassistant.const import CONF_ENABLED, CONF_METHOD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import condition
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.common import CallRecord
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.delivery import Delivery

from . import (
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_TARGETS_REQUIRED,
    ConditionVariables,
    DeliveryConfig,
    Target,
)

_LOGGER = logging.getLogger(__name__)


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
        deliveries: ConfigType | None = None,
        delivery_defaults: DeliveryConfig | ConfigType | None = None,
        targets_required: bool | None = True,
        device_domain: list[str] | None = None,
        device_discovery: bool | None = False,
        enabled: bool = True,
    ) -> None:
        self.hass: HomeAssistant = hass
        self.context: Context = context
        if isinstance(delivery_defaults, dict):
            delivery_defaults = DeliveryConfig(delivery_defaults)  # test support
        self.delivery_defaults: DeliveryConfig = delivery_defaults or DeliveryConfig({})
        self.targets_required: bool | None = targets_required
        self.device_domain: list[str] = device_domain or []
        self.device_discovery: bool | None = device_discovery
        self.enabled = enabled

        self.default_delivery: Delivery | None = None
        self.valid_deliveries: dict[str, Delivery] = {}
        self._delivery_configs: ConfigType = deliveries or {}

    async def initialize(self) -> None:
        """Async post-construction initialization"""
        if self.method is None:
            raise ValueError("No delivery method configured")
        self.valid_deliveries = await self.initialize_deliveries()
        if self.device_discovery:
            for domain in self.device_domain:
                discovered: int = 0
                added: int = 0
                for d in self.context.discover_devices(domain):
                    discovered += 1
                    if d.id not in self.delivery_defaults.target.device_id:
                        _LOGGER.info(f"SUPERNOTIFY Discovered device {d.name} for {domain}, id {d.id}")
                        self.delivery_defaults.target.device_id.append(d.id)
                        added += 1

                _LOGGER.info(f"SUPERNOTIFY device discovery for {domain} found {discovered} devices, added {added} new ones")

    @property
    def targets(self) -> Target:
        return self.delivery_defaults.target

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if delivery method has fixed action or doesn't require one"""
        return action is None or action.startswith("notify.")

    async def initialize_deliveries(self) -> dict[str, Delivery]:
        """Validate and initialize deliveries at startup for this method"""
        valid_deliveries: dict[str, Delivery] = {}

        for d, dc in self._delivery_configs.items():
            if dc.get(CONF_METHOD) != self.method:
                # this *should* only happen in unit tests
                _LOGGER.warning(f"SUPERNOTIFY Unexpected delivery {d} for method {self.method}")
                continue
            # don't care about ENABLED here since disabled deliveries can be overridden later
            delivery = Delivery(d, dc, self)
            if not await delivery.validate(self.context):
                _LOGGER.error(f"SUPERNOTIFY Ignoring delivery {d} with errors")
            else:
                valid_deliveries[d] = delivery

                if delivery.default and not self.default_delivery:
                    # pick the first delivery with default flag set as the default
                    self.default_delivery = delivery
                elif delivery.default and self.default_delivery and delivery.name != self.default_delivery.name:
                    _LOGGER.debug("SUPERNOTIFY Multiple default deliveries, skipping %s", d)

        if not self.default_delivery:
            method_definition: DeliveryConfig = self.delivery_defaults
            if method_definition:
                _LOGGER.info("SUPERNOTIFY Building default delivery for %s from method %s", self.method, method_definition)
                self.default_delivery = Delivery(f"DEFAULT_{self.method}", {}, self)
            else:
                _LOGGER.debug("SUPERNOTIFY No default delivery or method_definition for method %s", self.method)

        _LOGGER.debug(
            "SUPERNOTIFY Validated method %s, default delivery %s, default action %s, valid deliveries: %s",
            self.method,
            self.default_delivery,
            self.delivery_defaults.action,
            valid_deliveries,
        )
        return valid_deliveries

    def attributes(self) -> dict[str, Any]:
        return {
            CONF_METHOD: self.method,
            CONF_ENABLED: self.enabled,
            CONF_TARGETS_REQUIRED: self.targets_required,
            CONF_DEVICE_DOMAIN: self.device_domain,
            CONF_DEVICE_DISCOVERY: self.device_discovery,
            CONF_DELIVERY_DEFAULTS: self.delivery_defaults,
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

    def delivery_config(self, delivery_name: str) -> Delivery:
        return self.valid_deliveries.get(delivery_name) or self.default_delivery or Delivery("", {}, self)

    def set_action_data(self, action_data: dict[str, Any], key: str, data: Any | None) -> Any:
        if data is not None:
            action_data[key] = data
        return action_data

    async def evaluate_delivery_conditions(
        self, delivery_config: Delivery, condition_variables: ConditionVariables | None
    ) -> bool | None:
        if not self.enabled:
            return False
        if delivery_config.condition is None:
            return True

        try:
            test = await condition.async_from_config(self.hass, delivery_config.condition)
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
        delivery: Delivery = self.delivery_config(envelope.delivery_name)
        try:
            qualified_action = qualified_action or delivery.action
            if qualified_action and (action_data.get(ATTR_TARGET) or not self.targets_required or target_data):
                domain, service = qualified_action.split(".", 1)
                start_time = time.time()
                if target_data:
                    envelope.calls.append(
                        CallRecord(time.time() - start_time, domain, service, dict(action_data), dict(target_data))
                    )
                    await self.hass.services.async_call(domain, service, service_data=action_data, target=target_data)
                else:
                    envelope.calls.append(CallRecord(time.time() - start_time, domain, service, dict(action_data), None))
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
            _LOGGER.exception("SUPERNOTIFY Failed to notify %s via %s, data=%s", self.method, qualified_action, action_data)
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
