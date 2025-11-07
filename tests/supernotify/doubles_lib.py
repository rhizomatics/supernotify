from pathlib import Path
from typing import Any

from homeassistant.components import image
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from custom_components.supernotify import CONF_PERSON, CONF_TRANSPORT
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notify import TRANSPORTS
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.transport import Transport


class DummyTransport(Transport):
    transport = "dummy"

    def __init__(
        self,
        hass: HomeAssistant,
        context: Context,
        people_registry: PeopleRegistry,
        deliveries: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        deliveries = deliveries or {"dummy": {CONF_TRANSPORT: "dummy"}}
        super().__init__(hass, context, people_registry, deliveries, **kwargs)
        self.test_calls: list[Envelope] = []

    def validate_action(self, action: str | None) -> bool:
        return action is None

    def recipient_target(self, recipient: dict[str, Any]) -> Target | None:
        if recipient:
            person: str | None = recipient.get(CONF_PERSON)
            if person:
                return Target({ATTR_ENTITY_ID: [person.replace("person.", "dummy.")]})
        return None

    async def deliver(self, envelope: Envelope) -> bool:
        self.test_calls.append(envelope)
        envelope.delivered = True
        return True


class BrokenTransport(Transport):
    transport = "broken"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    @property
    def target_required(self) -> bool:
        return False

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


def build_delivery_from_config(conf: ConfigType, hass: HomeAssistant, ctx: Context, p_r: PeopleRegistry) -> dict[str, Delivery]:
    def transport(transport_name: str) -> Transport:
        return next(t for t in TRANSPORTS if t.transport == transport_name)(hass, ctx, p_r)

    return {k: Delivery(k, v, transport(v[CONF_TRANSPORT])) for k, v in conf.items()}
