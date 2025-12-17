# mypy: disable-error-code="name-defined"

import logging
import time
from abc import abstractmethod
from traceback import format_exception
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from homeassistant.components.notify.const import ATTR_TARGET
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_NAME,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from custom_components.supernotify.common import CallRecord
from custom_components.supernotify.context import Context
from custom_components.supernotify.model import DeliveryConfig, SuppressionReason, Target, TargetRequired, TransportConfig

from . import ATTR_ENABLED, CONF_DELIVERY_DEFAULTS, CONF_DEVICE_DISCOVERY, CONF_DEVICE_DOMAIN

if TYPE_CHECKING:
    import datetime as dt

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
        transport_config = transport_config or {}
        self.transport_config = TransportConfig(transport_config, class_config=self.default_config)

        self.delivery_defaults: DeliveryConfig = self.transport_config.delivery_defaults
        self.device_domain: list[str] = self.transport_config.device_domain or []
        self.device_model_include: list[str] | None = self.transport_config.device_model_include
        self.device_model_exclude: list[str] | None = self.transport_config.device_model_exclude
        self.device_discovery: bool | None = self.transport_config.device_discovery
        self.enabled = self.transport_config.enabled
        self.override_enabled = self.enabled
        self.alias = self.transport_config.alias
        self.last_error_at: dt.datetime | None = None
        self.last_error_in: str | None = None
        self.last_error_message: str | None = None
        self.error_count: int = 0

    async def initialize(self) -> None:
        """Async post-construction initialization"""
        if self.name is None:
            raise ValueError("No transport configured")

        if self.device_discovery:
            for domain in self.device_domain:
                discovered: int = 0
                added: int = 0
                for d in self.hass_api.discover_devices(
                    domain, device_model_include=self.device_model_include, device_model_exclude=self.device_model_exclude
                ):
                    discovered += 1
                    if self.delivery_defaults.target is None:
                        self.delivery_defaults.target = Target()
                    if d.id not in self.delivery_defaults.target.device_ids:
                        _LOGGER.info(f"SUPERNOTIFY Discovered {d.model} device {d.name} for {domain}, id {d.id}")
                        self.delivery_defaults.target.extend(ATTR_DEVICE_ID, d.id)
                        added += 1

                _LOGGER.info(f"SUPERNOTIFY device discovery for {domain} found {discovered} devices, added {added} new ones")

    @property
    def targets(self) -> Target:
        return self.delivery_defaults.target if self.delivery_defaults.target is not None else Target()

    @property
    def default_config(self) -> TransportConfig:
        return TransportConfig()

    @property
    def auto_configure(self) -> bool:
        return False

    def media_requirements(self, data: dict[str, Any]) -> dict[str, Any] | None:  # noqa: ARG002
        """Create a MEDIA_SCHEMA dict from media requirements implied in the data"""
        return None

    def validate_action(self, action: str | None) -> bool:
        """Override in subclass if transport has fixed action or doesn't require one"""
        return action == self.delivery_defaults.action

    def attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            ATTR_NAME: self.name,
            ATTR_ENABLED: self.override_enabled,
            CONF_DEVICE_DOMAIN: self.device_domain,
            CONF_DEVICE_DISCOVERY: self.device_discovery,
            CONF_DELIVERY_DEFAULTS: self.delivery_defaults,
        }
        if self.alias:
            attrs[ATTR_FRIENDLY_NAME] = self.alias
        if self.last_error_at:
            attrs["last_error_at"] = self.last_error_at.isoformat()
            attrs["last_error_in"] = self.last_error_in
            attrs["last_error_message"] = self.last_error_message
        attrs["error_count"] = self.error_count
        return attrs

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

    async def call_action(
        self,
        envelope: "Envelope",  # noqa: F821 # type: ignore
        qualified_action: str | None = None,
        action_data: dict[str, Any] | None = None,
        target_data: dict[str, Any] | None = None,
        implied_target: bool = False,  # True if the qualified action implies a target
    ) -> bool:
        action_data = action_data or {}
        start_time = time.time()
        domain = service = None
        delivery: Delivery = envelope.delivery
        try:
            qualified_action = qualified_action or delivery.action
            if not qualified_action:
                _LOGGER.debug(
                    "SUPERNOTIFY skipping %s action call with no service, targets %s",
                    envelope.delivery.name,
                    action_data.get(ATTR_TARGET),
                )
                envelope.skipped = 1
                envelope.skip_reason = SuppressionReason.NO_ACTION
                return False
            if (
                delivery.target_required == TargetRequired.ALWAYS
                and not action_data.get(ATTR_TARGET)
                and not action_data.get(ATTR_ENTITY_ID)
                and not implied_target
                and not target_data
            ):
                _LOGGER.debug(
                    "SUPERNOTIFY skipping %s action call for service %s, missing targets",
                    envelope.delivery.name,
                    qualified_action,
                )
                envelope.skipped = 1
                envelope.skip_reason = SuppressionReason.NO_TARGET
                return False

            domain, service = qualified_action.split(".", 1)
            start_time = time.time()
            if target_data:
                # home-assistant messes with the service_data passed by ref
                service_data_as_sent = dict(action_data)
                service_response = await self.hass_api.call_service(
                    domain, service, service_data=action_data, target_data=target_data, debug=delivery.debug
                )
                envelope.calls.append(
                    CallRecord(
                        time.time() - start_time,
                        domain,
                        service,
                        debug=delivery.debug,
                        action_data=service_data_as_sent,
                        target_data=target_data,
                        service_response=service_response,
                    )
                )
            else:
                service_data_as_sent = dict(action_data)
                service_response = await self.hass_api.call_service(
                    domain, service, service_data=action_data, debug=delivery.debug
                )
                envelope.calls.append(
                    CallRecord(
                        time.time() - start_time,
                        domain,
                        service,
                        debug=delivery.debug,
                        action_data=service_data_as_sent,
                        service_response=service_response,
                    )
                )

            envelope.delivered = 1
            return True
        except Exception as e:
            self.record_error(str(e), method="call_action")
            envelope.failed_calls.append(
                CallRecord(time.time() - start_time, domain, service, action_data, target_data, exception=str(e))
            )
            _LOGGER.exception("SUPERNOTIFY Failed to notify %s via %s, data=%s", self.name, qualified_action, action_data)
            envelope.errored += 1
            envelope.delivery_error = format_exception(e)
            return False

    def record_error(self, message: str, method: str) -> None:
        self.last_error_at = dt_util.utcnow()
        self.last_error_message = message
        self.last_error_in = method
        self.error_count += 1

    def simplify(self, text: str | None, strip_urls: bool = False) -> str | None:
        """Simplify text for delivery transports with speaking or plain text interfaces"""
        if not text:
            return None
        if strip_urls:
            words = text.split()
            text = " ".join(word for word in words if not urlparse(word).scheme)
        text = text.translate(str.maketrans("_", " ", "()£$<>"))
        _LOGGER.debug("SUPERNOTIFY Simplified text to: %s", text)
        return text
