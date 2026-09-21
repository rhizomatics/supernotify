from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.helpers import entity_registry as er

from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import EnvelopeOutcome
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall


class FakeAlexaMediaNotifyService:
    """Stand-in for alandtse/alexa_media_player's AlexaNotificationService.

    Mirrors the real integration's shape: the generic notify.alexa_media service and every
    auto-generated per-device alias (notify.alexa_media_<device>) are the *same* bound
    method. A per-device alias looks itself up in registered_targets and always speaks
    through that hard-coded device, ignoring whatever target: the caller actually passed -
    only the generic service honors target:.
    """

    def __init__(self) -> None:
        self.registered_targets: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    async def service_call(self, call: ServiceCall) -> None:
        if call.service in self.registered_targets:
            target = [self.registered_targets[call.service]]
        else:
            target = call.data.get("target")
        self.calls.append({"service": call.service, "target": target})


# find_service() matches a bound method by its instance's class's __module__ (that's how
# it recognises the real integration's AlexaNotificationService, defined in
# custom_components.alexa_media.notify) - fake that here too
FakeAlexaMediaNotifyService.__module__ = "custom_components.alexa_media.notify"


@pytest.fixture
async def support_case_fixture(hass: HomeAssistant):
    """https://github.com/rhizomatics/supernotify/issues/198

    Reproduces a real alandtse/alexa_media_player install: one generic notify.alexa_media
    service plus one auto-generated per-device alias per Echo. Before the fix,
    AlexaMediaPlayerTransport.default_config() (via HomeAssistantAPI.find_service())
    discovered whichever of these happened to register first - always a per-device alias,
    since the real integration registers those before the generic service - and used it as
    the action for every alexa_media_player delivery regardless of that delivery's own
    target, so every announcement played on the same one physical device.
    """
    svc = FakeAlexaMediaNotifyService()

    # registration order matches the real integration (homeassistant/components/notify/
    # legacy.py: async_register_services() registers per-target aliases first, the generic
    # service is only registered afterwards, if not already present)
    for alias, entity_id in (
        ("alexa_media_office_echo", "media_player.office_echo"),
        ("alexa_media_kitchen_echo", "media_player.kitchen_echo"),
        ("alexa_media_bedroom_echo", "media_player.bedroom_echo"),
    ):
        svc.registered_targets[alias] = entity_id
        hass.services.async_register("notify", alias, svc.service_call)
    hass.services.async_register("notify", "alexa_media", svc.service_call)

    # the alexa_media_player transport only selects media_player entities registered by the
    # alexa_media integration itself (not e.g. a Chromecast) - register these in the entity
    # registry with platform "alexa_media" so target selection recognises them
    entity_registry = er.async_get(hass)
    for entity_id in ("media_player.kitchen_echo", "media_player.bedroom_echo", "media_player.office_echo"):
        object_id = entity_id.split(".", 1)[1]
        entity_registry.async_get_or_create("media_player", "alexa_media", object_id, suggested_object_id=object_id)

    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
    delivery:
      tts_kitchen_echo:
        transport: alexa_media_player
        target: [media_player.kitchen_echo]
        options:
          media_auto_pause: false
      tts_bedroom_echo:
        transport: alexa_media_player
        target: [media_player.bedroom_echo]
        options:
          media_auto_pause: false
      tts_office_echo:
        transport: alexa_media_player
        target: [media_player.office_echo]
        options:
          media_auto_pause: false
""",
    )
    ctx.fake_alexa_service = svc  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
    await ctx.test_initialize()
    return ctx


async def test_kitchen_delivery_calls_generic_service_with_kitchen_target(support_case_fixture, hass: HomeAssistant) -> None:
    uut = Notification(support_case_fixture, "Kitchen test", action_data={"delivery": "tts_kitchen_echo"})
    await uut.initialize()
    await uut.deliver()
    await hass.async_block_till_done()

    envelope = uut.deliveries["tts_kitchen_echo"][EnvelopeOutcome.SUCCESS][0]  # type: ignore
    call = envelope.calls[0]  # type: ignore
    assert call.domain == "notify"
    assert call.action == "alexa_media", "should resolve to the generic, target-respecting service, not a per-device alias"
    assert call.action_data["target"] == ["media_player.kitchen_echo"]  # type: ignore[index] # ty: ignore[not-subscriptable]

    assert support_case_fixture.fake_alexa_service.calls == [
        {"service": "alexa_media", "target": ["media_player.kitchen_echo"]}
    ]


async def test_bedroom_and_office_deliveries_route_to_their_own_targets(support_case_fixture, hass: HomeAssistant) -> None:
    """Reproduces the reported symptom: kitchen, bedroom and office deliveries all ended up
    calling notify.alexa_media_office_echo regardless of their own target."""
    for delivery, entity_id in (
        ("tts_bedroom_echo", "media_player.bedroom_echo"),
        ("tts_office_echo", "media_player.office_echo"),
    ):
        uut = Notification(support_case_fixture, "test", action_data={"delivery": delivery})
        await uut.initialize()
        await uut.deliver()
        await hass.async_block_till_done()

        envelope = uut.deliveries[delivery][EnvelopeOutcome.SUCCESS][0]  # type: ignore
        call = envelope.calls[0]  # type: ignore
        assert call.action == "alexa_media"
        assert call.action_data["target"] == [entity_id]  # type: ignore[index]  # ty: ignore[not-subscriptable]

    assert [c["service"] for c in support_case_fixture.fake_alexa_service.calls] == ["alexa_media", "alexa_media"]
    assert [c["target"] for c in support_case_fixture.fake_alexa_service.calls] == [
        ["media_player.bedroom_echo"],
        ["media_player.office_echo"],
    ]
