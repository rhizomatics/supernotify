from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock, call

import aiofiles
from homeassistant.components import camera, image
from homeassistant.core import Context as HAContext
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from PIL import Image, ImageDraw, ImageStat

from custom_components.supernotify.const import CONF_TRANSPORT
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.engine import TRANSPORTS
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.model import TargetRequired, TransportConfig
from custom_components.supernotify.transport import Transport

if TYPE_CHECKING:
    from collections.abc import Callable

    import voluptuous as vol
    from anyio import Path
    from homeassistant.helpers.typing import ConfigType

    from custom_components.supernotify.context import Context
    from custom_components.supernotify.envelope import Envelope
    from custom_components.supernotify.notification import DebugTrace

# a small palette of maximally-distinct colors, one per camera, stamped as a solid block onto
# that camera's still - see MockCameraEntity. Flat blocks survive the JPEG re-encode
# in write_image_from_bitmap almost losslessly (unlike fine detail or text), so a plain nearest-
# color match on the block's average is a cheap, reliable way to tell two cameras' images apart
# after the full round trip through the delivery pipeline.
_CAMERA_MARKER_COLORS: list[tuple[int, int, int]] = [
    (220, 20, 60),  # crimson
    (30, 144, 255),  # dodger blue
    (50, 205, 50),  # lime green
    (255, 165, 0),  # orange
    (148, 0, 211),  # dark violet
]
_CAMERA_MARKER_BOX = (0, 0, 96, 96)  # top-left corner, clear of the format-label text in fixtures/media


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
        module: str | None = None,
    ) -> None:
        self.hass = hass
        self.calls: list[ServiceCall] = []
        self.supports_response: SupportsResponse = supports_response
        self.exception = exception
        self.action: str = action
        self.domain: str = domain
        self.schema = schema
        self.response: ServiceResponse | None = response
        self.job = Mock()
        self.job.target = Mock()
        self.job.target.__module__ = module  # type: ignore
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

    def is_viable(self, hass_api: HomeAssistantAPI) -> bool:
        return True

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


class MockCameraEntity(camera.Camera):
    """A camera whose image is the file at filename, or without one, the example image with a
    marker block in a color picked by index, so it can be told apart from other cameras' images
    even after being resized or re-encoded on the way through the delivery pipeline"""

    _attr_name = "Test"

    def __init__(self, filename: Path | None = None, name: str = "porch", area_id: str | None = None, index: int = 0) -> None:
        super().__init__()
        self.filename = filename
        self.camera_name = name
        self.area_id = area_id
        self.marker_color: tuple[int, int, int] | None = (
            None if filename else _CAMERA_MARKER_COLORS[index % len(_CAMERA_MARKER_COLORS)]
        )
        self.image_size: tuple[int, int] | None = None

    def register(self, hass: HomeAssistant) -> str:
        """Add the camera to the entity registry, in its area if it has one, returning its entity_id"""
        entity_registry = er.async_get(hass)
        entry = entity_registry.async_get_or_create(
            "camera", "generic", f"{self.camera_name}_id", suggested_object_id=self.camera_name
        )
        if self.area_id:
            entity_registry.async_update_entity(entry.entity_id, area_id=self.area_id)
        hass.states.async_set(entry.entity_id, "idle")
        return entry.entity_id

    async def load(self) -> None:
        if self.filename:
            async with aiofiles.open(self.filename, "rb") as f:
                self.bytes = await f.read()
        elif self.marker_color:
            # conftest imports this module, so it can only be imported from here
            from conftest import test_image

            image = Image.open(str(test_image().path)).convert("RGB")
            ImageDraw.Draw(image).rectangle(_CAMERA_MARKER_BOX, fill=self.marker_color)
            buffer = BytesIO()
            image.save(buffer, format="JPEG")
            self.bytes = buffer.getvalue()
            self.image_size = image.size

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        return self.bytes

    def produced(self, image_data: bytes) -> bool:
        """Whether an image came from this camera, by its marker color being the nearest in the palette"""
        assert self.marker_color is not None and self.image_size is not None, "Only cameras without a file are marked"
        image = Image.open(BytesIO(image_data)).convert("RGB")
        # scale the marker box to the image, in case it was resized, and sample its middle away from JPEG edge bleed
        x_scale, y_scale = image.width / self.image_size[0], image.height / self.image_size[1]
        left, top, right, bottom = _CAMERA_MARKER_BOX
        sample = ImageStat.Stat(
            image.crop((
                int((left + right) / 4 * x_scale),
                int((top + bottom) / 4 * y_scale),
                int((left + right) * 3 / 4 * x_scale),
                int((top + bottom) * 3 / 4 * y_scale),
            ))
        ).mean

        def distance(color: tuple[int, int, int]) -> float:
            return sum((a - b) ** 2 for a, b in zip(sample, color, strict=True))

        return min(_CAMERA_MARKER_COLORS, key=distance) == self.marker_color


def build_delivery_from_config(conf: ConfigType, ctx: Context) -> dict[str, Delivery]:
    def transport(transport_name: str) -> Transport:
        return next(t for t in TRANSPORTS if t.name == transport_name)(ctx)

    return {k: Delivery(k, v, transport(v[CONF_TRANSPORT])) for k, v in conf.items()}
