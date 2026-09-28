"""Tests for build_standard_deliveries() across transports that can be auto-discovered
from an existing Home Assistant config entry (telegram, ntfy, kodi, lametric,
alexa_devices), a dynamically-named notify service (discord, pushover, sms), or
unconditionally (persistent).

`Transport.inclusion_mode` no longer exists as a per-transport property - instead
`Transport.default_config` (transport.py) infers `inclusion` from whether the
transport declares `unique_target_categories`/`fallback_target_categories` at all
(`default_inclusion()`, transport.py): `default` if it does, `explicit` if it
doesn't, since a transport that can never definitively claim anything has no way to
prove a given notification is relevant to it. `Notification.select_deliveries()`
then still matches those categories against the notification's target/recipients at
selection time (see notification.py's `_category_satisfied()`) - `default` alone
isn't enough for a standard delivery to actually get auto-selected. Transports whose
target is positively identifiable (an HA entity_id, a recipient's email/phone, or a
value qualified with a category no other transport uses, like `discord_channel`/
`matrix_room`/`topic`/`telegram_chat_id`) declare one of those lists, so a qualified
value is unambiguous. mqtt's `topic` can equally be a `data:` keyword instead of a
target (`target_required` is `optional`, so plain NO_TARGET can't short-circuit it)
- Notification._target_required() is what actually keeps its standard delivery from
firing unprompted, by treating it as if target_required were `always` whenever it's
both implicit (never named by a call, scenario or recipient) and auto-generated
(not a user's own CONFIG delivery, which may deliberately rely on a fixed `data:`
topic).

Transports whose target category is itself ambiguous (kodi, tts, and the generic
`media` transport all match a bare `media_player` entity, so there's no reliable
way to tell which one a given entity was meant for), that declare no target
category at all (ntfy, lametric, pushover, gotify), or where firing unprompted
would simply be unwelcome (persistent) - declare no unique/fallback categories, so
`default_inclusion()` infers `explicit` for them, same as before this mechanism
existed, without needing to say so per-transport any more.

Path in upstream repo:
    tests/components/supernotify/transports/test_transport_auto_configure.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]
from pytest_unordered import unordered

from custom_components.supernotify.const import (
    INCLUSION_DEFAULT,
    INCLUSION_EXPLICIT,
    TRANSPORT_ALEXA,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_CHIME,
    TRANSPORT_DISCORD,
    TRANSPORT_GENERIC,
    TRANSPORT_GOTIFY,
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
from custom_components.supernotify.transports.alexa_devices import (
    STANDARD_DELIVERY_ANNOUNCE_ALL,
    STANDARD_DELIVERY_SPEAK_ALL,
)
from custom_components.supernotify.transports.chime import OPTION_CHIME_ALIASES, STANDARD_DELIVERY_SIREN_ALL
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# transport name -> HA config entry domain it should discover, shared by the viability
# test below and (bar mqtt/telegram, both `default` - see test_mqtt_auto_configure_with_
# config_entry_is_default/test_telegram_auto_configure_with_config_entry_is_default) by
# test_auto_configure_with_config_entry_never_matches. alexa_devices and html5 are
# tested separately (test_transport_alexa_devices.py / test_transport_html5.py) - both
# also require an actual registered notify entity with a matching platform, not just
# the config entry, to auto-configure as `default`.
CONFIG_ENTRY_EXPLICIT = {
    TRANSPORT_KODI: "kodi",
    TRANSPORT_TELEGRAM: "telegram_bot",
    TRANSPORT_NTFY: "ntfy",
    TRANSPORT_LAMETRIC: "lametric",
    TRANSPORT_MQTT: "mqtt",
}


@pytest.mark.parametrize(("transport_name", "domain"), CONFIG_ENTRY_EXPLICIT.items())
async def test_auto_configure_no_config_entry(hass: HomeAssistant, transport_name: str, domain: str) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(transport_name, force=True)
    assert not uut.is_viable(ctx.hass_api)


@pytest.mark.parametrize(
    ("transport_name", "domain"),
    {k: v for k, v in CONFIG_ENTRY_EXPLICIT.items() if k not in (TRANSPORT_MQTT, TRANSPORT_TELEGRAM)}.items(),
)
async def test_auto_configure_with_config_entry_never_matches(hass: HomeAssistant, transport_name: str, domain: str) -> None:
    entry = MockConfigEntry(domain=domain, data={})
    entry.add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(transport_name)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert transport_name in result
    dc = DeliveryConfig(result[transport_name], uut.delivery_defaults)
    # declaring no unique/fallback categories means default_inclusion() infers explicit
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_telegram_auto_configure_with_config_entry_is_default(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="telegram_bot", data={})
    entry.add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TELEGRAM)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_TELEGRAM in result
    # a telegram_chat_id isn't positively identifiable by shape, but it's a dedicated
    # category no other transport uses, so a qualified value is unambiguous
    dc = DeliveryConfig(result[TRANSPORT_TELEGRAM], uut.delivery_defaults)
    assert dc.inclusion == [INCLUSION_DEFAULT]


async def test_mqtt_auto_configure_with_config_entry_is_default(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain="mqtt", data={})
    entry.add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MQTT)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_MQTT in result
    # a topic string isn't positively identifiable by shape, but `topic` is a dedicated
    # category no other transport uses, so a qualified value is unambiguous. Being implicit
    # and OPTIONAL is safe here because Notification._target_required() treats an
    # implicit-only, auto-generated OPTIONAL delivery with target_categories as ALWAYS.
    dc = DeliveryConfig(result[TRANSPORT_MQTT], uut.delivery_defaults)
    assert dc.inclusion == [INCLUSION_DEFAULT]


async def test_discord_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_DISCORD, force=True)
    assert uut.build_standard_deliveries(ctx.hass_api) == {}


async def test_discord_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "homeassistant.components.discord.notify"
    hass.services.async_register("notify", "discord_2", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_DISCORD)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_DISCORD in result
    dc = DeliveryConfig(result["discord"], uut.delivery_defaults)
    assert dc.action == "notify.discord_2"
    # a discord channel/user ID isn't positively identifiable by shape, but
    # discord_channel is a dedicated category no other transport uses, so a qualified
    # value is unambiguous
    assert dc.inclusion == [INCLUSION_DEFAULT]


async def test_pushover_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER, force=True)
    assert uut.build_standard_deliveries(ctx.hass_api) == {}


async def test_pushover_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "homeassistant.components.pushover.notify"
    hass.services.async_register("notify", "pushover_home", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PUSHOVER)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_PUSHOVER in result
    dc = DeliveryConfig(result["pushover"], uut.delivery_defaults)
    assert dc.action == "notify.pushover_home"
    # a pushover device/group isn't positively identifiable, so no unique/fallback
    # categories are declared and default_inclusion() infers explicit
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_sms_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS, force=True)
    assert uut.build_standard_deliveries(ctx.hass_api) == {}


async def test_sms_auto_configure_discovers_twilio_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "homeassistant.components.twilio_sms.notify"
    hass.services.async_register("notify", "twilio_sms", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_SMS in result
    dc = DeliveryConfig(result["sms"], uut.delivery_defaults)
    assert dc.action == "notify.twilio_sms"
    # phone number is positively identified via the recipient's registered phone, so default
    assert INCLUSION_DEFAULT in dc.inclusion


async def test_sms_auto_configure_discovers_mikrotik_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "custom_components.mikrotik_sms.notify"
    hass.services.async_register("notify", "mikrotik_sms", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_SMS)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_SMS in result
    dc = DeliveryConfig(result["sms"], uut.delivery_defaults)
    assert dc.action == "notify.mikrotik_sms"
    assert INCLUSION_DEFAULT in dc.inclusion


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

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_SMS in result
    dc = DeliveryConfig(result["sms"], uut.delivery_defaults)
    assert dc.action == "notify.twilio_sms"


async def test_persistent_auto_configure_always_available_but_explicit(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_PERSISTENT)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_PERSISTENT in result
    # persistent_notification is always available in HA core, no integration to discover,
    # and declares no unique/fallback categories, so default_inclusion() infers explicit -
    # a UI popup on every notification would be intrusive anyway
    dc = DeliveryConfig(result["persistent"], uut.delivery_defaults)
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_tts_auto_configure_no_service_no_media_player(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS, force=True)
    assert not uut.is_viable(ctx.hass_api)


async def test_tts_auto_configure_service_without_media_player(hass: HomeAssistant) -> None:
    hass.services.async_register("tts", "speak", lambda call: None)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS, force=True)
    assert not uut.is_viable(ctx.hass_api)


async def test_tts_auto_configure_media_player_without_service(hass: HomeAssistant) -> None:
    hass.states.async_set("media_player.kitchen", "idle")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS, force=True)
    assert not uut.is_viable(ctx.hass_api)


async def test_tts_auto_configure_service_and_media_player_is_explicit(hass: HomeAssistant) -> None:
    hass.services.async_register("tts", "speak", lambda call: None)
    hass.states.async_set("media_player.kitchen", "idle")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_TTS)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_TTS in result
    # media_player is only an other_target_category for tts (kodi/media share the same
    # ambiguous domain), which never drives auto-selection, so default_inclusion() infers
    # explicit
    dc = DeliveryConfig(result["tts"], uut.delivery_defaults)
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_media_player_auto_configure_no_media_players(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MEDIA, force=True)
    assert not uut.is_viable(ctx.hass_api)


async def test_media_player_auto_configure_with_media_player_is_explicit(hass: HomeAssistant) -> None:
    hass.states.async_set("media_player.kitchen", "idle")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MEDIA)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_MEDIA in result
    # media_player is only an other_target_category here (kodi/tts share the same
    # ambiguous domain), which never drives auto-selection, so default_inclusion() infers
    # explicit
    dc = DeliveryConfig(result["media"], uut.delivery_defaults)
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_alexa_media_player_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA_MEDIA_PLAYER, force=True)
    assert uut.build_standard_deliveries(ctx.hass_api) == {}


async def test_alexa_media_player_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "custom_components.alexa_media.notify"
    hass.services.async_register("notify", "alexa_media", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA_MEDIA_PLAYER)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_ALEXA_MEDIA_PLAYER in result
    dc = DeliveryConfig(result["alexa_media_player"], uut.delivery_defaults)
    assert dc.action == "notify.alexa_media"
    # media_player is only an other_target_category here (shared, ambiguous with kodi/
    # tts/media), which never drives auto-selection, so default_inclusion() infers explicit
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_alexa_devices_stays_default_without_alexa_media_player(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)
    er.async_get(hass).async_get_or_create("notify", "alexa_devices", "bedroom_echo_unique_id")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_ALEXA in result
    dc = DeliveryConfig(result["alexa_devices"], uut.delivery_defaults)
    assert INCLUSION_DEFAULT in dc.inclusion


async def test_alexa_devices_speak_all_and_announce_all_conditional(hass: HomeAssistant) -> None:
    """The extra "..._speak_all"/"..._announce_all" standard deliveries only appear when
    at least one notify entity matches the naming convention, and only include the
    matching entities - not every alexa_devices notify entity."""
    MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create("notify", "alexa_devices", "bedroom_speak_id", suggested_object_id="bedroom_echo_speak")
    ent_reg.async_get_or_create("notify", "alexa_devices", "kitchen_announce_id", suggested_object_id="kitchen_echo_announce")
    ent_reg.async_get_or_create("notify", "alexa_devices", "hall_id", suggested_object_id="hall_echo")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA)

    result = uut.build_standard_deliveries(ctx.hass_api)
    speak = DeliveryConfig(result["alexa_devices_speak_all"], uut.delivery_defaults)
    assert speak.target is not None
    assert speak.target.entity_ids == ["notify.bedroom_echo_speak"]
    assert speak.inclusion == [INCLUSION_EXPLICIT]
    announce = DeliveryConfig(result["alexa_devices_announce_all"], uut.delivery_defaults)
    assert announce.target is not None
    assert announce.target.entity_ids == ["notify.kitchen_echo_announce"]
    assert announce.inclusion == [INCLUSION_EXPLICIT]


async def test_alexa_devices_excludes_speaker_groups(hass: HomeAssistant) -> None:
    """A speaker group gets its own "_announce"/"_speak" notify entities alongside its
    member devices' own, but can't be expanded to its members - so it's excluded
    entirely to avoid double notification of the same group members."""
    config_entry = MockConfigEntry(domain="alexa_devices", data={})
    config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    member_device = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("alexa_devices", "bedroom_echo")}, model="Echo Dot"
    )
    ent_reg.async_get_or_create(
        "notify",
        "alexa_devices",
        "bedroom_speak_id",
        suggested_object_id="bedroom_echo_speak",
        device_id=member_device.id,
    )
    ent_reg.async_get_or_create(
        "notify",
        "alexa_devices",
        "bedroom_announce_id",
        suggested_object_id="bedroom_echo_announce",
        device_id=member_device.id,
    )

    group_device = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("alexa_devices", "family_room_group")}, model="Speaker Group"
    )
    ent_reg.async_get_or_create(
        "notify",
        "alexa_devices",
        "family_room_speak_id",
        suggested_object_id="family_room_speak",
        device_id=group_device.id,
    )
    ent_reg.async_get_or_create(
        "notify",
        "alexa_devices",
        "family_room_announce_id",
        suggested_object_id="family_room_announce",
        device_id=group_device.id,
    )

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA)

    result = uut.build_standard_deliveries(ctx.hass_api)
    speak = DeliveryConfig(result["alexa_devices_speak_all"], uut.delivery_defaults)
    assert speak.target is not None
    assert speak.target.entity_ids == ["notify.bedroom_echo_speak"]
    announce = DeliveryConfig(result["alexa_devices_announce_all"], uut.delivery_defaults)
    assert announce.target is not None
    assert announce.target.entity_ids == ["notify.bedroom_echo_announce"]


async def test_alexa_devices_no_speak_or_announce_extras_without_matching_entities(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)
    er.async_get(hass).async_get_or_create("notify", "alexa_devices", "hall_id", suggested_object_id="hall_echo")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_ALEXA)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert STANDARD_DELIVERY_SPEAK_ALL not in result
    assert STANDARD_DELIVERY_ANNOUNCE_ALL not in result


async def test_chime_auto_configure_no_aliases(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    # always viable (an explicit delivery can supply its own chime_aliases) - but with no
    # transport-level default, there's nothing to auto-generate a delivery from
    uut = ctx.transport(TRANSPORT_CHIME, force=True)
    assert uut.is_viable(ctx.hass_api)
    assert TRANSPORT_CHIME not in uut.build_standard_deliveries(ctx.hass_api)


async def test_chime_auto_configure_with_aliases_configured(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_CHIME, force=True)
    uut.delivery_defaults.options[OPTION_CHIME_ALIASES] = {"alexa_devices": "bell01"}

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_CHIME in result
    assert result[TRANSPORT_CHIME] == {}


async def test_chime_siren_all_created_when_sirens_exist(hass: HomeAssistant) -> None:
    hass.states.async_set("siren.hallway", "off")
    hass.states.async_set("siren.garage", "off")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_CHIME, force=True)

    result = uut.build_standard_deliveries(ctx.hass_api)
    dc = DeliveryConfig(result["chime_siren_all"], uut.delivery_defaults)
    assert dc.target is not None
    assert dc.target.entity_ids == unordered(["siren.hallway", "siren.garage"])
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_chime_no_siren_all_without_sirens(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_CHIME, force=True)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert STANDARD_DELIVERY_SIREN_ALL not in result


async def test_gotify_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY, force=True)
    assert uut.build_standard_deliveries(ctx.hass_api) == {}


async def test_gotify_auto_configure_discovers_service(hass: HomeAssistant) -> None:
    def _send_message(call: object) -> None:
        return None

    _send_message.__module__ = "custom_components.gotify.notify"
    hass.services.async_register("notify", "gotify", _send_message)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GOTIFY)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_GOTIFY in result
    dc = DeliveryConfig(result["gotify"], uut.delivery_defaults)
    assert dc.action == "notify.gotify"
    # gotify declares no unique/fallback categories, so default_inclusion() infers explicit
    assert dc.inclusion == [INCLUSION_EXPLICIT]


async def test_matrix_auto_configure_no_service(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MATRIX, force=True)
    assert not uut.is_viable(ctx.hass_api)


async def test_matrix_auto_configure_service_registered_is_default(hass: HomeAssistant) -> None:
    hass.services.async_register("matrix", "send_message", lambda call: None)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MATRIX)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_MATRIX in result
    # a room ID/alias isn't positively identifiable by shape, but matrix_room is a
    # dedicated category no other transport uses, so a qualified value is unambiguous
    dc = DeliveryConfig(result, uut.delivery_defaults)
    assert dc.inclusion == [INCLUSION_DEFAULT]


async def test_mobile_push_auto_configure_no_config_entry(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH, force=True)
    assert not uut.is_viable(ctx.hass_api)


async def test_mobile_push_auto_configure_with_config_entry_stays_default(hass: HomeAssistant) -> None:
    MockConfigEntry(domain="mobile_app", data={}).add_to_hass(hass)

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_MOBILE_PUSH)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_MOBILE_PUSH in result
    dc = DeliveryConfig(result, uut.delivery_defaults)
    assert INCLUSION_DEFAULT in dc.inclusion


async def test_notify_entity_auto_configure_no_notify_entities(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NOTIFY_ENTITY, force=True)
    assert not uut.is_viable(ctx.hass_api)


async def test_notify_entity_auto_configure_with_notify_entity_stays_default(hass: HomeAssistant) -> None:
    hass.states.async_set("notify.mock_notify_target", "unknown")

    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_NOTIFY_ENTITY)

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_NOTIFY_ENTITY in result
    dc = DeliveryConfig(result, uut.delivery_defaults)
    assert INCLUSION_DEFAULT in dc.inclusion


async def test_generic_auto_configure_no_action(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    # always viable (entirely delivery-driven, no transport-level prerequisite) - but with
    # no default action, there's nothing to auto-generate a delivery from
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
    assert uut.is_viable(ctx.hass_api)
    assert TRANSPORT_GENERIC not in uut.build_standard_deliveries(ctx.hass_api)


async def test_generic_auto_configure_with_action_configured(hass: HomeAssistant) -> None:
    ctx = TestingContext(homeassistant=hass)
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_GENERIC, force=True)
    uut.delivery_defaults.action = "notify.my_chat_server"

    result = uut.build_standard_deliveries(ctx.hass_api)
    assert TRANSPORT_GENERIC in result
    assert result[TRANSPORT_GENERIC] == {}
