# mypy: disable-error-code="name-defined"

import logging
import time
from abc import abstractmethod
from traceback import format_exception
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from homeassistant.components.notify.const import ATTR_TARGET
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_ENABLED
from homeassistant.helpers.typing import ConfigType

from custom_components.supernotify.common import CallRecord
from custom_components.supernotify.context import Context
from custom_components.supernotify.model import ConditionVariables, DeliveryConfig, Target, TargetRequired, TransportConfig

from . import (
    CONF_DELIVERY_DEFAULTS,
    CONF_DEVICE_DISCOVERY,
    CONF_DEVICE_DOMAIN,
    CONF_TRANSPORT,
)

if TYPE_CHECKING:
    from .delivery import Delivery, DeliveryRegistry
    from .hass_api import HomeAssistantAPI
    from .people import PeopleRegistry

_LOGGER = logging.getLogger(__name__)


class Transport:
    """Base class for delivery transports.

    Sub classes integrste with Home Assistant notification services
    or alternative notification mechanisms.
    """

    name: str

    @abstractmethod
    def __init__(self, context: Context, transport_config: ConfigType | None = None) -> None:
        self.hass_api: HomeAssistantAPI = context.hass_api
        self.people_registry: PeopleRegistry = context.people_registry
        self.delivery_registry: DeliveryRegistry = context.delivery_registry
        self.context: Context = context

        self.transport_config = TransportConfig(
            transport_config or {}, class_config=self.default_config)

        self.delivery_defaults: DeliveryConfig = self.transport_config.delivery_defaults
        self.device_domain: list[str] = self.transport_config.device_domain or [
        ]
        self.device_discovery: bool | None = self.transport_config.device_discovery
        self.enabled = self.transport_config.enabled

    async def initialize(self) -> None:
        """Async post-construction initialization"""
        if self.name is None:
            raise ValueError("No transport configured")

        if self.device_discovery:
            for domain in self.device_domain:
                discovered: int = 0
                added: int = 0
                for d in self.hass_api.discover_devices(domain):
                    discovered += 1
                    if self.delivery_defaults.target is None:
                        self.delivery_defaults.target = Target()
                    if d.id not in self.delivery_defaults.target.device_ids:
                        _LOGGER.info(
                            f"SUPERNOTIFY Discovered device {d.name} for {domain}, id {d.id}")
                        self.delivery_defaults.target.extend(
                            ATTR_DEVICE_ID, d.id)
                        added += 1

                _LOGGER.info(
                    f"SUPERNOTIFY device discovery for {domain} found {discovered} devices, added {added} new ones")

    @property
    def targets(self) -> Target:
        return self.delivery_defaults.target if self.delivery_defaults.target is not None else Target()

    @property
    def default_config(self) -> TransportConfig:
        return TransportConfig()

    @property
    def auto_configure(self) -> bool:
        return False

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action == self.delivery_defaults.action

    def attributes(self) -> dict[str, Any]:
        return {
            CONF_TRANSPORT: self.name,
            CONF_ENABLED: self.enabled,
            CONF_DEVICE_DOMAIN: self.device_domain,
            CONF_DEVICE_DISCOVERY: self.device_discovery,
            CONF_DELIVERY_DEFAULTS: self.delivery_defaults,
        }

    @abstractmethod
    async def deliver(self, envelope: "Envelope") -> bool:  # noqa: F821 # type: ignore
        """Delivery implementation

        Args:
        ----
            envelope (Envelope): envelope to be delivered

        """

    def set_action_data(self, action_data: dict[str, Any], key: str, data: Any | None) -> Any:
        if data is not None:
            action_data[key] = data
        return action_data

    async def evaluate_delivery_conditions(
        self, delivery: "Delivery", condition_variables: ConditionVariables | None
    ) -> bool | None:
        if not self.enabled:
            return False
        if delivery.condition is None:
            return True

        return await self.hass_api.evaluate_condition(delivery.condition, condition_variables)

    async def call_action(
        self,
        envelope: "Envelope",  # noqa: F821 # type: ignore
        qualified_action: str | None = None,
        action_data: dict[str, Any] | None = None,
        target_data: dict[str, Any] | None = None,
        implied_target: bool = False  # True if the qualified action implies a target
    ) -> bool:
        action_data = action_data or {}
        start_time = time.time()
        domain = service = None
        delivery: Delivery = envelope.delivery
        try:
            qualified_action = qualified_action or delivery.action
            if qualified_action and (
                action_data.get(ATTR_TARGET) or action_data.get(
                    ATTR_ENTITY_ID) or implied_target or delivery.target_required != TargetRequired.ALWAYS or target_data
            ):
                domain, service = qualified_action.split(".", 1)
                start_time = time.time()
                if target_data:
                    envelope.calls.append(
                        CallRecord(time.time() - start_time, domain,
                                   service, dict(action_data), dict(target_data))
                    )
                    # TODO: add a debug mode with return response and blocking True
                    await self.hass_api.call_service(domain, service, service_data=action_data, target_data=target_data)
                else:
                    envelope.calls.append(CallRecord(
                        time.time() - start_time, domain, service, dict(action_data), None))
                    await self.hass_api.call_service(domain, service, service_data=action_data)
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
                CallRecord(time.time() - start_time, domain, service,
                           action_data, target_data, exception=str(e))
            )
            _LOGGER.exception("SUPERNOTIFY Failed to notify %s via %s, data=%s",
                              self.name, qualified_action, action_data)
            envelope.errored += 1
            envelope.delivery_error = format_exception(e)
            return False

    def simplify(self, text: str | None, strip_urls: bool = False) -> str | None:
        """Simplify text for delivery transports with speaking or plain text interfaces"""
        if not text:
            return None
        if strip_urls:
            words = text.split()
            text = " ".join(
                word for word in words if not urlparse(word).scheme)
        text = text.translate(str.maketrans("_", " ", "()£$<>"))
        _LOGGER.debug("SUPERNOTIFY Simplified text to: %s", text)
        return text
