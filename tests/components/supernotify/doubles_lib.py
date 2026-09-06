from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, call

import aiofiles
from homeassistant.components import image
from homeassistant.core import Context as HAContext
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.util import dt as dt_util

from custom_components.supernotify.const import CONF_TRANSPORT
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.model import TargetRequired, TransportConfig
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from collections.abc import Callable

    import voluptuous as vol
    from anyio import Path
    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.context import Context
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.notification import DebugTrace


def service_call(
    domain: str,
    service: str,
    service_data: dict[str, Any] | None = None,
    blocking: bool = False,
    context: HAContext | None = None,
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

    MOCKED_SERVICES: dict[tuple[str, str], Callable] = {}  # noqa: RUF012

    def __init__(
        self,
        hass: HomeAssistant | None,
        domain: str = "notify",
        action: str = "custom_test",
        supports_response: SupportsResponse = SupportsResponse.NONE,
        schema: vol.Schema | None = None,
        response: ServiceResponse | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.hass = hass
        self.calls: list[ServiceCall] = []
        self.supports_response: SupportsResponse = supports_response
        self.exception = exception
        self.action: str = action
        self.domain: str = domain
        self.schema = schema
        self.response: ServiceResponse | None = response
        if hass is not None:
            if isinstance(hass, Mock):
                DummyService.MOCKED_SERVICES[domain, action] = self.mocked_service_call
                hass.services.async_call.side_effect = self.service_delegator
            else:
                hass.services.async_register(
                    domain, action, self.service_call, schema=schema, supports_response=supports_response
                )

    @classmethod
    def service_delegator(cls, domain: str, action: str, **kwargs: Any) -> ServiceResponse | None:
        service: Callable = cls.MOCKED_SERVICES[domain, action]
        return service(domain, action, **kwargs)

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
        return_response = (
            False if return_response is None or self.supports_response == SupportsResponse.NONE else return_response
        )
        service_data = dict(service_data) if service_data else {}
        service_data.update(target or {})
        if self.hass is not None:
            self.calls.append(ServiceCall(self.hass, domain, service, service_data, context, return_response))
        if self.exception:
            raise self.exception
        if return_response:
            return self.response
        return None

    def service_call(self, call: ServiceCall) -> ServiceResponse | None:
        self.calls.append(call)
        if self.exception:
            raise self.exception
        if self.supports_response != SupportsResponse.NONE:
            return self.response
        return None


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
        self.filename = filename

    async def load(self) -> None:
        async with aiofiles.open(self.filename, "rb") as f:
            self.bytes = await f.read()

    async def async_added_to_hass(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        return self.bytes


def build_delivery_from_config(conf: ConfigType, ctx: Context) -> dict[str, Delivery]:
    def transport(transport_name: str) -> Transport:
        return next(t for t in TRANSPORTS if t.name == transport_name)(ctx)

    return {k: Delivery(k, v, transport(v[CONF_TRANSPORT])) for k, v in conf.items()}
