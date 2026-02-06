from pathlib import Path
from typing import Any
from unittest.mock import Mock, call

from homeassistant.components import image
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from custom_components.supernotify.const import CONF_TRANSPORT
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import TargetRequired, TransportConfig
from custom_components.supernotify.notification import DebugTrace
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.transport import Transport


def service_call(
    domain: str,
    service: str,
    service_data: dict[str, Any] | None = None,
    blocking: bool = False,
    context: Any = None,
    target: dict[str, Any] | None = None,
    return_response: bool = False,
):
    return call(
        domain,
        service,
        service_data=service_data or {},
        target=target,
        context=context,
        return_response=return_response,
        blocking=blocking,
    )


class DummyService:
    """Dummy service for testing purposes."""

    def __init__(
        self,
        hass: HomeAssistant | None,
        domain: str = "notify",
        action: str = "custom_test",
        supports_response=SupportsResponse.OPTIONAL,
        response: ServiceResponse | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.hass = hass
        self.calls: list[ServiceCall] = []
        self.response = response
        self.exception = exception
        self.action = action
        self.domain = domain
        if hass is not None:
            if isinstance(hass, Mock):
                hass.services.async_call.side_effect = self.mocked_service_call
            else:
                hass.services.async_register(domain, action, self.service_call, supports_response=supports_response)

    def mocked_service_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None,
        blocking: bool = False,
        context=None,
        target=None,
        return_response: bool | None = None,
    ) -> ServiceResponse | None:
        return_response = False if return_response is None else return_response
        service_data = service_data or {}
        service_data.update(target or {})
        if self.hass is not None:
            self.calls.append(ServiceCall(self.hass, domain, service, service_data, context, return_response))
        if self.exception:
            raise self.exception
        return self.response

    def service_call(self, call: ServiceCall) -> ServiceResponse | None:
        self.calls.append(call)
        if self.exception:
            raise self.exception
        return self.response


class DummyTransport(Transport):
    name = "dummy"

    def __init__(
        self,
        *args: Any,
        service_exception: Exception | None = None,
        transport_exception: Exception | None = None,
        target_required: TargetRequired = TargetRequired.ALWAYS,
        **kwargs: Any,
    ) -> None:
        self.target_required = target_required
        super().__init__(*args, **kwargs)
        self.service = DummyService(self.hass_api._hass, exception=service_exception)
        self.action = f"{self.service.domain}.{self.service.action}"
        self.transport_exception = transport_exception

    def validate_action(self, action: str | None) -> bool:
        return action is None

    @property
    def default_config(self) -> TransportConfig:
        config = TransportConfig()
        config.delivery_defaults.target_required = self.target_required
        return config

    async def deliver(self, envelope: Envelope, debug_trace: DebugTrace | None = None) -> bool:
        if self.transport_exception:
            raise self.transport_exception
        return await self.call_action(
            envelope,
            self.action,
            action_data=envelope.data,
            target_data=envelope.target.direct().as_dict() if envelope.target else None,
        )


class MockImageEntity(image.ImageEntity):
    _attr_name = "Test"

    def __init__(self, filename: Path):
        self.bytes = filename.open("rb").read()

    async def async_added_to_hass(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        return self.bytes


def build_delivery_from_config(conf: ConfigType, ctx: Context) -> dict[str, Delivery]:
    def transport(transport_name: str) -> Transport:
        return next(t for t in TRANSPORTS if t.name == transport_name)(ctx)

    return {k: Delivery(k, v, transport(v[CONF_TRANSPORT])) for k, v in conf.items()}
