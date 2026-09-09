r"""Reproduction tests for GitHub issue #10 - some transports won't select group entity ids.

2026-09-09: written as FAILING regression tests before the fix. Every assertion below describes
the EXPECTED (fixed) behaviour, so these tests fail on current main and must pass once the fix lands.

Mechanism under test:
- ``Delivery.select_targets`` applies the transport default ``target_select`` regex
  (e.g. ``media_player\\.[A-Za-z0-9_]+``) and silently drops any ``group.*`` entity id before the
  transport ever sees it.
- Even if a ``group.*`` id got through, ``MediaPlayerTransport`` / ``AlexaMediaPlayerTransport`` /
  ``NotifyEntityTransport`` never expand it. Only ``ChimeTransport`` calls
  ``hass_api.expand_group`` (-> ``homeassistant.helpers.group.expand_entity_ids``), which keeps
  non-group ids untouched and swaps ``group.*`` ids for their ``entity_id`` attribute members.
- Home Assistant entity services (``media_player.play_media``, ``notify.send_message``) expand
  ``group.*`` in ``target.entity_id`` themselves (``async_extract_referenced_entity_ids`` with
  ``expand_group=True``), so for those two transports letting the group id through the selector
  is enough. ``notify.alexa_media`` is a legacy notify service with ``target`` in the service data,
  so it gets no native expansion and the transport has to expand explicitly (it also needs the
  member players for its volume snapshot / restore logic).

The end-to-end tests accept either fix strategy: the group id being passed through to a service
that will expand it natively, or the transport expanding to member entity ids itself.
"""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import ATTR_ENTITY_ID
from pytest_unordered import unordered

from custom_components.supernotify.const import (
    ATTR_DELIVERY,
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_URL,
    CONF_DATA,
    CONF_TRANSPORT,
    TRANSPORT_ALEXA_MEDIA_PLAYER,
    TRANSPORT_CHIME,
    TRANSPORT_MEDIA,
    TRANSPORT_NOTIFY_ENTITY,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transport import Transport
from custom_components.supernotify.transports.alexa_media_player import AlexaMediaPlayerTransport
from custom_components.supernotify.transports.chime import ChimeTransport
from custom_components.supernotify.transports.media_player import MediaPlayerTransport
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport
from tests.components.supernotify.hass_setup_lib import MockGroup, TestingContext

SPEAKER_GROUP = "group.living_room_speakers"
SPEAKERS = ["media_player.echo_1", "media_player.echo_2"]
NOTIFY_GROUP = "group.all_phones"
NOTIFIERS = ["notify.phone_1", "notify.phone_2"]


def _service_targets(context: TestingContext, domain: str, service: str) -> list[str]:
    """Entity ids targeted by calls to domain.service, with any group ids expanded the same way
    HA's own entity service layer would expand them (so either fix strategy is accepted)."""
    found: list[str] = []
    for c in context.hass.services.async_call.call_args_list:  # type: ignore[attr-defined]
        if c.args[:2] != (domain, service):
            continue
        target: dict[str, Any] = c.kwargs.get("target") or {}
        entity_ids = target.get(ATTR_ENTITY_ID) or c.kwargs.get("service_data", {}).get("target") or []
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        found.extend(context.hass_api.expand_group(entity_ids))
    return found


# ---------------------------------------------------------------------------------------------
# (a) Delivery.select_targets drops group.* for transports with a domain-restricted target_select
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("transport_class", "group_id", "member"),
    [
        (MediaPlayerTransport, SPEAKER_GROUP, "media_player.hall"),
        (AlexaMediaPlayerTransport, SPEAKER_GROUP, "media_player.hall"),
        (NotifyEntityTransport, NOTIFY_GROUP, "notify.pong"),
    ],
    ids=["media_player", "alexa_media_player", "notify_entity"],
)
async def test_select_targets_keeps_group_entity_id(transport_class: type[Transport], group_id: str, member: str) -> None:
    """EXPECTED: a group.* entity id is expanded into its members by the transport default target
    selection, alongside a directly matching entity id. CURRENT: the default target_select regex only
    admits the transport's own domain, so the group id is silently dropped."""
    domain = member.partition(".")[0]
    members = [f"{domain}.grouped_1", f"{domain}.grouped_2"]
    ctx = TestingContext(transport_types=[transport_class], entities={group_id: MockGroup(members)})
    await ctx.test_initialize()
    uut = Delivery("unit_testing", {}, transport_class(ctx, {}))

    selected = uut.select_targets(Target([group_id, member, "switch.not_for_this_transport"]))

    assert selected.entity_ids == unordered(*members, member)


# ---------------------------------------------------------------------------------------------
# (b) End-to-end: media_player transport with a group target
# ---------------------------------------------------------------------------------------------


async def test_media_player_delivers_to_group_members() -> None:
    """EXPECTED: notifying target=group.x via the media transport plays the image on every member
    media_player (either by passing the group through for HA to expand, or by expanding itself).
    CURRENT: the group id is filtered out at delivery selection, no play_media call is made."""
    ctx = TestingContext(
        deliveries={"alexa_show": {CONF_TRANSPORT: TRANSPORT_MEDIA}},
        transport_types=[MediaPlayerTransport],
        entities={SPEAKER_GROUP: MockGroup(SPEAKERS)},
        hass_external_url="https://myserver",
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "hello there",
        target=SPEAKER_GROUP,
        action_data={ATTR_DELIVERY: {"alexa_show": {CONF_DATA: {ATTR_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/ftp/pic.jpeg"}}}}},
    )
    await uut.initialize()
    await uut.deliver()

    assert len(uut.delivered_envelopes) == 1, f"deliveries: {uut.deliveries}"
    assert _service_targets(ctx, "media_player", "play_media") == unordered(*SPEAKERS)


# ---------------------------------------------------------------------------------------------
# (c) End-to-end: alexa_media_player and notify_entity transports with a group target
# ---------------------------------------------------------------------------------------------


async def test_alexa_media_player_delivers_to_group_members() -> None:
    """EXPECTED: notifying target=group.x via alexa_media_player announces on every member.
    notify.alexa_media is a legacy notify service (target in service data, not an entity target),
    so HA will NOT expand the group natively - the transport must expand to member media_players.
    CURRENT: the group id is filtered out at delivery selection, no notify.alexa_media call is made."""
    ctx = TestingContext(
        deliveries={"announce": {CONF_TRANSPORT: TRANSPORT_ALEXA_MEDIA_PLAYER}},
        transport_types=[AlexaMediaPlayerTransport],
        entities={SPEAKER_GROUP: MockGroup(SPEAKERS)},
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "hello there",
        target=SPEAKER_GROUP,
        action_data={ATTR_DELIVERY: {"announce": {CONF_DATA: {"pause_music": False}}}},
    )
    await uut.initialize()
    await uut.deliver()

    assert len(uut.delivered_envelopes) == 1, f"deliveries: {uut.deliveries}"
    announce_calls = [
        c
        for c in ctx.hass.services.async_call.call_args_list
        if c.args[:2] == ("notify", "alexa_media")  # type: ignore[attr-defined]
    ]
    assert announce_calls, "no notify.alexa_media call made"
    announced: list[str] = []
    for c in announce_calls:
        announced.extend(c.kwargs["service_data"]["target"])
    # explicit member expansion required here, a raw group id would be meaningless to notify.alexa_media
    assert announced == unordered(*SPEAKERS)


async def test_notify_entity_delivers_to_group_members() -> None:
    """EXPECTED: notifying target=group.x (a group of notify entities) via notify_entity sends to
    every member. notify.send_message is an entity service, so HA expands group.* in
    target.entity_id natively - passing the group id through is sufficient.
    CURRENT: the group id is filtered out at delivery selection, no notify.send_message call is made."""
    ctx = TestingContext(
        deliveries={"phones": {CONF_TRANSPORT: TRANSPORT_NOTIFY_ENTITY}},
        transport_types=[NotifyEntityTransport],
        entities={NOTIFY_GROUP: MockGroup(NOTIFIERS)},
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "hello there", title="testing", target=NOTIFY_GROUP)
    await uut.initialize()
    await uut.deliver()

    assert len(uut.delivered_envelopes) == 1, f"deliveries: {uut.deliveries}"
    assert _service_targets(ctx, "notify", "send_message") == unordered(*NOTIFIERS)


# ---------------------------------------------------------------------------------------------
# (d) Control: chime transport already selects and expands group targets
# ---------------------------------------------------------------------------------------------


async def test_chime_control_selects_and_expands_group() -> None:
    """Reference behaviour that the other transports should match: chime's target_select admits
    group.* and deliver() expands the group via hass_api.expand_group. Now that groups are expanded at
    delivery target selection, the selector yields the members and chime's own expansion is a no-op."""
    ctx = TestingContext(
        deliveries={"chimes": {CONF_TRANSPORT: TRANSPORT_CHIME, CONF_DATA: {"chime_tune": "ding"}}},
        transport_types=[ChimeTransport],
        entities={SPEAKER_GROUP: MockGroup(SPEAKERS)},
    )
    await ctx.test_initialize()

    # selector expands the group into its members
    assert ctx.delivery("chimes").select_targets(Target([SPEAKER_GROUP])).entity_ids == unordered(*SPEAKERS)

    uut = Notification(ctx, target=SPEAKER_GROUP)
    await uut.initialize()
    await uut.deliver()

    assert len(uut.delivered_envelopes) == 1
    # chime issues one play_media per expanded member, never for the group id itself
    assert _service_targets(ctx, "media_player", "play_media") == unordered(*SPEAKERS)


async def test_expand_group_keeps_plain_and_unknown_ids() -> None:
    """Documents the HA expand_entity_ids contract the fix can rely on: non-group ids pass through
    unchanged (lowercased), a group id is replaced by its members, and a group with no state is
    dropped rather than kept. Passes on current main."""
    ctx = TestingContext(entities={SPEAKER_GROUP: MockGroup(SPEAKERS)})
    await ctx.test_initialize()

    assert ctx.hass_api.expand_group(["media_player.solo", SPEAKER_GROUP, "group.does_not_exist"]) == [
        "media_player.solo",
        *SPEAKERS,
    ]
