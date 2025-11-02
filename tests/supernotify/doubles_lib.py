from pathlib import Path
from typing import Any

from homeassistant.components import image
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from custom_components.supernotify import CONF_METHOD, CONF_PERSON
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notify import METHODS


class DummyDeliveryMethod(DeliveryMethod):
    method = "dummy"

    def __init__(self, hass: HomeAssistant, context: Context, deliveries: dict[str, Any] | None = None, **kwargs: Any) -> None:
        deliveries = deliveries or {"dummy": {CONF_METHOD: "dummy"}}
        super().__init__(hass, context, deliveries, **kwargs)
        self.test_calls: list[Envelope] = []

    def validate_action(self, action: str | None) -> bool:
        return action is None

    def recipient_target(self, recipient: dict[str, Any]) -> list[str]:
        if recipient:
            person: str | None = recipient.get(CONF_PERSON)
            if person:
                return [person.replace("person.", "dummy.")]
        return []

    async def deliver(self, envelope: Envelope) -> bool:
        self.test_calls.append(envelope)
        envelope.delivered = True
        return True


class BrokenDeliveryMethod(DeliveryMethod):
    method = "broken"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def validate_action(self, action: str | None) -> bool:
        return True

    async def deliver(self, envelope: Envelope) -> bool:
        raise OSError("a self-inflicted error has occurred")


class MockImageEntity(image.ImageEntity):
    _attr_name = "Test"

    def __init__(self, filename: Path):
        self.bytes = filename.open("rb").read()

    async def async_added_to_hass(self) -> None:
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        return self.bytes


def build_delivery_from_config(conf: ConfigType, hass: HomeAssistant, ctx: Context) -> dict[str, Delivery]:
    def method(method_name: str) -> DeliveryMethod:
        return next(m for m in METHODS if m.method == method_name)(hass, ctx)

    return {k: Delivery(k, v, method(v[CONF_METHOD])) for k, v in conf.items()}
