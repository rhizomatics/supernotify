"""Tests for auto_configure() across transports that can be auto-discovered from
an existing Home Assistant config entry (telegram, ntfy, kodi, lametric,
alexa_devices), a dynamically-named notify service (discord, pushover, sms), or
unconditionally (persistent).

Transports whose target is positively identifiable (an HA entity_id, or a
recipient's email/phone) generate a "DEFAULT_" delivery that fires on every
notification. Transports that need an opaque per-delivery identifier the
notification author must still supply (chat_id, channel/user ID, device_id) -
or where firing unprompted would simply be unwelcome (persistent) - generate a
plain, explicit-selection-only delivery instead, named after the transport.

Path in upstream repo:
    tests/components/supernotify/transports/test_transport_auto_configure.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify.const import (
    OPTION_CHIME_ALIASES,
    SELECTION_DEFAULT,
    SELECTION_EXPLICIT,
    TRANSPORT_ALEXA,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_CHIME,
    TRANSPORT_DISCORD,
    TRANSPORT_GENERIC,
    TRANSPORT_GOTIFY,
    TRANSPORT_HTML5,
    TRANSPORT_KODI,
    TRANSPORT_LAMETRIC,
    TRANSPORT_MATRIX,
    TRANSPORT_MEDIA,
    TRANSPORT_MOBILE_PUSH,
    TRANSPORT_MQTT,
    TRANSPORT_NOTIFY_ENTITY,
    TRANSPORT_NTFY,
    TRANSPORT_PERSISTENT,
    TRANSPORT_PUSHOVER,
    TRANSPORT_SMS,
    TRANSPORT_TELEGRAM,
    TRANSPORT_TTS,
)
from custom_components.supernotify.model import DeliveryConfig
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# transport name -> HA config entry domain it should discover, for transports whose
# target is positively identifiable (an entity_id) and so fire by default once found
CONFIG_ENTRY_DEFAULT = {
    TRANSPORT_KODI: "kodi",
    TRANSPORT_ALEXA: "alexa_devices",
}

# transport name -> HA config entry domain it should discover, for transports that
# need an opaque per-delivery identifier (chat_id/device_id) and so stay explicit-only
CONFIG_ENTRY_EXPLICIT = {
    TRANSPORT_TELEGRAM: "telegram_bot",
    TRANSPORT_NTFY: "ntfy",
    TRANSPORT_LAMETRIC: "lametric",
    TRANSPORT_MQTT: "mqtt",
    TRANSPORT_HTML5: "html5",
}


@pytest.mark.parametrize(("transport_name", "domain"), {**CONFIG_ENTRY_DEFAULT, **CONFIG_ENTRY_EXPLICIT}.items())
async def test_auto_configure_no_config_entry(hass: HomeAssistant, transport_name: str, domain: str) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(transport_name)
    assert uut.auto_configure(ctx.hass_api) is None


@pytest.mark.parametrize(("transport_name", "domain"), CONFIG_ENTRY_DEFAULT.items())
async def test_auto_configure_with_config_entry_stays_default(hass: HomeAssistant, transport_name: str, domain: str) -> None:
    entry = MockConfigEntry(domain=domain, data={})
    entry.add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(transport_name)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert SELECTION_DEFAULT in result.selection


@pytest.mark.parametrize(("transport_name", "domain"), CONFIG_ENTRY_EXPLICIT.items())
async def test_auto_configure_with_config_entry_is_explicit(hass: HomeAssistant, transport_name: str, domain: str) -> None:
    entry = MockConfigEntry(domain=domain, data={})
    entry.add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(transport_name)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.selection == [SELECTION_EXPLICIT]


async def test_discord_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_DISCORD)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_discord_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "homeassistant.components.discord.notify"
    hass.services.async_register("notify", "discord_2", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_DISCORD)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.action == "notify.discord_2"
    # a discord channel/user ID isn't positively identifiable, so explicit-only
    assert result.selection == [SELECTION_EXPLICIT]


async def test_pushover_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_pushover_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "homeassistant.components.pushover.notify"
    hass.services.async_register("notify", "pushover_home", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.action == "notify.pushover_home"
    # once discovered the service is fully self-contained (target_required=NEVER), so default
    assert SELECTION_DEFAULT in result.selection


async def test_sms_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_sms_auto_configure_discovers_twilio_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "homeassistant.components.twilio_sms.notify"
    hass.services.async_register("notify", "twilio_sms", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.action == "notify.twilio_sms"
    # phone number is positively identified via the recipient's registered phone, so default
    assert SELECTION_DEFAULT in result.selection


async def test_sms_auto_configure_discovers_mikrotik_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "custom_components.mikrotik_sms.notify"
    hass.services.async_register("notify", "mikrotik_sms", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.action == "notify.mikrotik_sms"
    assert SELECTION_DEFAULT in result.selection


async def test_sms_auto_configure_prefers_twilio_over_mikrotik(hass: HomeAssistant) -> None:
    def _twilio_send(call: object) -> None:
        return None

    def _mikrotik_send(call: object) -> None:
        return None

    _twilio_send.__module__ = "homeassistant.components.twilio_sms.notify"
    _mikrotik_send.__module__ = "custom_components.mikrotik_sms.notify"
    hass.services.async_register("notify", "twilio_sms", _twilio_send)
    hass.services.async_register("notify", "mikrotik_sms", _mikrotik_send)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.action == "notify.twilio_sms"


async def test_persistent_auto_configure_always_available_but_explicit(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PERSISTENT)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    # persistent_notification is always available in HA core, no integration to discover,
    # but a UI popup on every notification would be intrusive, so it's explicit-only
    assert result.selection == [SELECTION_EXPLICIT]


async def test_tts_auto_configure_no_service_no_media_player(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_tts_auto_configure_service_without_media_player(hass: HomeAssistant) -> None:
    hass.services.async_register("tts", "speak", lambda call: None)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_tts_auto_configure_media_player_without_service(hass: HomeAssistant) -> None:
    hass.states.async_set("media_player.kitchen", "idle")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_tts_auto_configure_service_and_media_player_is_explicit(hass: HomeAssistant) -> None:
    hass.services.async_register("tts", "speak", lambda call: None)
    hass.states.async_set("media_player.kitchen", "idle")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    # a media_player target is required per notification, so explicit-only
    assert result.selection == [SELECTION_EXPLICIT]


async def test_media_player_auto_configure_no_media_players(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MEDIA)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_media_player_auto_configure_with_media_player_is_explicit(hass: HomeAssistant) -> None:
    hass.states.async_set("media_player.kitchen", "idle")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MEDIA)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    # a media_player target is required per notification, so explicit-only
    assert result.selection == [SELECTION_EXPLICIT]


async def test_alexa_media_player_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA_MEDIA_PLAYER)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_alexa_media_player_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "custom_components.alexa_media.notify"
    hass.services.async_register("notify", "alexa_media", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA_MEDIA_PLAYER)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.action == "notify.alexa_media"
    # a channel/device ID isn't positively identifiable, so explicit-only
    assert result.selection == [SELECTION_EXPLICIT]


async def test_alexa_devices_stays_default_without_alexa_media_player(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert SELECTION_DEFAULT in result.selection


async def test_alexa_devices_goes_explicit_alongside_alexa_media_player(hass: HomeAssistant) -> None:
    """Both integrations notify the same physical Echo devices, so once Alexa Media
    Player is also available, Alexa Devices backs off to explicit-only to avoid
    double-notifying the same targets."""
    MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)

    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "custom_components.alexa_media.notify"
    hass.services.async_register("notify", "alexa_media", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.selection == [SELECTION_EXPLICIT]


async def test_chime_auto_configure_no_aliases(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_CHIME)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_chime_auto_configure_with_aliases_configured(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_CHIME)
    uut.delivery_defaults.options[OPTION_CHIME_ALIASES] = {"alexa_devices": "bell01"}

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result is uut.delivery_defaults


async def test_gotify_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_gotify_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "custom_components.gotify.notify"
    hass.services.async_register("notify", "gotify", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result.action == "notify.gotify"
    # once discovered the service is fully self-contained (target_required=NEVER), so default
    assert SELECTION_DEFAULT in result.selection


async def test_matrix_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MATRIX)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_matrix_auto_configure_service_registered_is_explicit(hass: HomeAssistant) -> None:
    hass.services.async_register("matrix", "send_message", lambda call: None)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MATRIX)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    # a room ID/alias isn't positively identifiable, so explicit-only
    assert result.selection == [SELECTION_EXPLICIT]


async def test_mobile_push_auto_configure_no_config_entry(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_mobile_push_auto_configure_with_config_entry_stays_default(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="mobile_app", data={}).add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert SELECTION_DEFAULT in result.selection


async def test_notify_entity_auto_configure_no_notify_entities(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NOTIFY_ENTITY)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_notify_entity_auto_configure_with_notify_entity_stays_default(hass: HomeAssistant) -> None:
    hass.states.async_set("notify.mock_notify_target", "unknown")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NOTIFY_ENTITY)

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert SELECTION_DEFAULT in result.selection


async def test_generic_auto_configure_no_action(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    assert uut.auto_configure(ctx.hass_api) is None


async def test_generic_auto_configure_with_action_configured(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC)
    uut.delivery_defaults.action = "notify.my_chat_server"

    result = cast("DeliveryConfig", uut.auto_configure(ctx.hass_api))
    assert result is not None
    assert result is uut.delivery_defaults
