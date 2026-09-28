"""Tests for the target-driven implicit delivery selection design (see transport.py's
unique_target_categories/fallback_target_categories/other_target_categories and
Notification.select_deliveries()'s "actual matching step").

Two things this design depends on that aren't exercised by any single transport's own
tests: that unique_target_categories really are unique across every registered transport
(nothing else could claim the same value), and that a notification carrying a value for
every kind of category selects exactly the deliveries that can definitively claim
something - no more, no less.
"""

from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]
from pytest_unordered import unordered

from custom_components.supernotify.const import (
    ATTR_DISCORD_CHANNEL,
    ATTR_EMAIL,
    ATTR_ENTITY_ID,
    ATTR_MATRIX_ROOM,
    ATTR_MOBILE_APP_ID,
    ATTR_PHONE,
    ATTR_TELEGRAM_CHAT_ID,
    ATTR_TOPIC,
)
from custom_components.supernotify.engine import TRANSPORTS
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.target import TargetEntityCategory
from custom_components.supernotify.transports.chime import OPTION_CHIME_ALIASES
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _categories_could_collide(a: TargetEntityCategory, b: TargetEntityCategory) -> bool:
    """Whether some real entity_id could satisfy both categories' domain/platform filters.

    `None` on either side of an axis means "no restriction there", so it never rules a
    collision out - matching TargetEntityCategory.matches()'s own only-filter-if-set logic.
    """

    def _could_overlap(x: str | list[str] | None, y: str | list[str] | None) -> bool:
        if x is None or y is None:
            return True
        xs = {x} if isinstance(x, str) else set(x)
        ys = {y} if isinstance(y, str) else set(y)
        return not xs.isdisjoint(ys)

    return _could_overlap(a.domain, b.domain) and _could_overlap(a.platform, b.platform)


async def test_unique_target_categories_dont_overlap_across_transports() -> None:
    """Structural guard: the whole target-driven selection design assumes unique_target_
    categories really are unique - if a future transport accidentally declares one another
    transport already owns, implicit selection could pick either one unpredictably."""
    ctx = TestingContext()
    await ctx.test_initialize()
    per_transport: dict[str, list[str | TargetEntityCategory]] = {
        t.name: ctx.transport(t.name, force=True).unique_target_categories for t in TRANSPORTS
    }

    for (name_a, categories_a), (name_b, categories_b) in combinations(per_transport.items(), 2):
        for category_a in categories_a:
            for category_b in categories_b:
                if isinstance(category_a, TargetEntityCategory) and isinstance(category_b, TargetEntityCategory):
                    assert not _categories_could_collide(category_a, category_b), (
                        f"{name_a} and {name_b} both claim entities matching {category_a!r}/{category_b!r}"
                    )
                elif not isinstance(category_a, TargetEntityCategory) and not isinstance(category_b, TargetEntityCategory):
                    assert category_a != category_b, f"{name_a} and {name_b} both claim category {category_a!r}"


async def _rich_context(hass: HomeAssistant) -> TestingContext:
    """A TestingContext with every unique/fallback-category transport viable, plus a
    handful of media_player-ambiguous ones (kodi/tts/media/chime) that should never
    implicitly select no matter what's in the target."""
    MockConfigEntry(domain="mobile_app", data={}).add_to_hass(hass)
    MockConfigEntry(domain="mqtt", data={}).add_to_hass(hass)
    MockConfigEntry(domain="telegram_bot", data={}).add_to_hass(hass)
    MockConfigEntry(domain="html5", data={}).add_to_hass(hass)
    MockConfigEntry(domain="alexa_devices", data={}).add_to_hass(hass)
    MockConfigEntry(domain="kodi", data={}).add_to_hass(hass)

    def _smtp_send(call: object) -> None:
        return None

    def _discord_send(call: object) -> None:
        return None

    def _alexa_media_send(call: object) -> None:
        return None

    def _twilio_send(call: object) -> None:
        return None

    _smtp_send.__module__ = "homeassistant.components.smtp.notify"
    _discord_send.__module__ = "homeassistant.components.discord.notify"
    _alexa_media_send.__module__ = "custom_components.alexa_media.notify"
    _twilio_send.__module__ = "homeassistant.components.twilio_sms.notify"
    hass.services.async_register("notify", "smtp", _smtp_send)
    hass.services.async_register("notify", "discord_1", _discord_send)
    hass.services.async_register("notify", "alexa_media", _alexa_media_send)
    hass.services.async_register("notify", "twilio_sms", _twilio_send)
    hass.services.async_register("matrix", "send_message", lambda call: None)
    hass.services.async_register("tts", "speak", lambda call: None)

    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create("notify", "html5", "html5-unique-id", suggested_object_id="unique_html5_browser")
    ent_reg.async_get_or_create("notify", "alexa_devices", "alexa-unique-id", suggested_object_id="unique_alexa_kitchen")
    hass.states.async_set("media_player.ambiguous_player", "idle")
    # notify_entity is only viable once at least one notify.* entity exists at all - this one
    # is deliberately unregistered (no platform), so it's only ever a fallback match
    hass.states.async_set("notify.plain_fallback_target", "unknown")

    ctx = TestingContext(
        homeassistant=hass,
        transports={
            "chime": {"delivery_defaults": {"options": {OPTION_CHIME_ALIASES: {"default": {"media_player": "bell01"}}}}}
        },
    )
    await ctx.test_initialize()
    return ctx


async def test_unique_target_categories_concrete_disambiguation(hass: HomeAssistant) -> None:
    """One blended target with one distinct, realistic value per declared unique category -
    each value's owning delivery, and only that one, claims it (exactly one claim each)."""
    ctx = await _rich_context(hass)

    target = {
        ATTR_EMAIL: ["unique.recipient@example.test"],
        ATTR_PHONE: ["+15551234567"],
        ATTR_MOBILE_APP_ID: ["mobile_app_unique_test_phone"],
        ATTR_DISCORD_CHANNEL: ["123456789012345678"],
        ATTR_MATRIX_ROOM: ["!uniqueroom:example.org"],
        ATTR_TOPIC: ["home/unique/topic"],
        ATTR_TELEGRAM_CHAT_ID: ["987654321"],
        ATTR_ENTITY_ID: ["notify.unique_html5_browser", "notify.unique_alexa_kitchen"],
    }

    uut = Notification(ctx, "testing 123", target=target)
    await uut.initialize()

    # notify_entity also candidates on the two notify.* entities via its fallback_target_
    # categories (domain="notify", no platform restriction) - that's expected, not a
    # uniqueness violation: it declares no unique_target_categories of its own, so it isn't
    # part of the invariant this test is guarding. Real exclusivity for these two specific
    # entities is still Target.select()'s job once a delivery is actually built.
    assert list(uut.selected_deliveries) == unordered(
        "email", "sms", "mobile_push", "discord", "matrix", "mqtt", "telegram", "html5", "alexa_devices", "notify_entity"
    )


async def test_unique_target_categories_concrete_disambiguation_via_flat_list_prefixes(hass: HomeAssistant) -> None:
    """The primary, documented way to give an ambiguous-by-shape value a category: a flat
    target list with a `category:value` prefix (e.g. `discord_channel:434343434`) - not the
    dict form the other tests here use. Values with a recognisable shape (email/phone/
    mobile_app_id/entity_id) need no prefix at all."""
    ctx = await _rich_context(hass)

    target = [
        "unique.recipient@example.test",
        "+15551234567",
        "mobile_app_unique_test_phone",
        "discord_channel:434343434",
        "matrix_room:!uniqueroom:example.org",
        "topic:home/unique/topic",
        "telegram_chat_id:215678938",
        "notify.unique_html5_browser",
        "notify.unique_alexa_kitchen",
    ]

    uut = Notification(ctx, "testing 123", target=target)
    await uut.initialize()

    assert list(uut.selected_deliveries) == unordered(
        "email", "sms", "mobile_push", "discord", "matrix", "mqtt", "telegram", "html5", "alexa_devices", "notify_entity"
    )


async def test_maximal_notification_selects_expected_deliveries(hass: HomeAssistant) -> None:
    """A notification carrying a value for every unique category, a fallback-only bare
    notify.* entity, and an ambiguous other-only media_player entity - selects exactly the
    unique/fallback matches, and none of the transports that only ever see media_player as
    an other_target_category (kodi/tts/media/chime/alexa_media_player never auto-select)."""
    ctx = await _rich_context(hass)

    target = {
        ATTR_EMAIL: ["unique.recipient@example.test"],
        ATTR_PHONE: ["+15551234567"],
        ATTR_MOBILE_APP_ID: ["mobile_app_unique_test_phone"],
        ATTR_DISCORD_CHANNEL: ["123456789012345678"],
        ATTR_MATRIX_ROOM: ["!uniqueroom:example.org"],
        ATTR_TOPIC: ["home/unique/topic"],
        ATTR_TELEGRAM_CHAT_ID: ["987654321"],
        ATTR_ENTITY_ID: [
            "notify.unique_html5_browser",
            "notify.unique_alexa_kitchen",
            "notify.plain_fallback_target",
            "media_player.ambiguous_player",
        ],
    }

    uut = Notification(ctx, "testing 123", target=target)
    await uut.initialize()

    assert list(uut.selected_deliveries) == unordered(
        "email", "sms", "mobile_push", "discord", "matrix", "mqtt", "telegram", "html5", "alexa_devices", "notify_entity"
    )
    for never_auto in ("kodi", "tts", "media", "chime", "alexa_media_player"):
        assert never_auto not in uut.selected_deliveries
