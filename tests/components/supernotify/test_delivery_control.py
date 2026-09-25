"""The Delivery Control options - defaults for deliveries that don't set their own"""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock

from homeassistant.const import CONF_ACTION

from custom_components.supernotify.const import (
    CONF_INCLUSION,
    CONF_OCCUPANCY,
    CONF_TRANSPORT,
    INCLUSION_DEFAULT,
    INCLUSION_EXPLICIT,
    OCCUPANCY_ALL,
    OCCUPANCY_ANY_IN,
    OCCUPANCY_ONLY_IN,
    TRANSPORT_GENERIC,
    TRANSPORT_MOBILE_PUSH,
    TRANSPORT_TTS,
)
from custom_components.supernotify.transports.generic import GenericTransport
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from custom_components.supernotify.transports.tts import TTSTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

DELIVERIES = {
    "chat": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.chat"},
    "phone": {CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH},
    "speaker": {CONF_TRANSPORT: TRANSPORT_TTS},
}


async def _registry(yaml: str = "", deliveries: dict | None = None, transports: dict | None = None) -> TestingContext:
    ctx = TestingContext(
        yaml=yaml or None,
        deliveries=deliveries or DELIVERIES,
        transports=transports,
        transport_types=[GenericTransport, TTSTransport],
        viable_transport_types=[MobilePushTransport],
    )
    ctx.hass_api.raise_issue = Mock()  # type: ignore[method-assign]
    await ctx.test_initialize()
    return ctx


async def test_unset_keeps_each_transports_own_defaults() -> None:
    ctx = await _registry()
    deliveries = ctx.delivery_registry.deliveries

    assert deliveries["chat"].inclusion == [INCLUSION_EXPLICIT]
    assert deliveries["phone"].inclusion == [INCLUSION_DEFAULT]
    assert deliveries["speaker"].occupancy == OCCUPANCY_ALL


async def test_default_inclusion_applies_to_every_delivery() -> None:
    ctx = await _registry(
        "delivery_control:\n  default_inclusion: explicit\n",
        deliveries={
            **DELIVERIES,
            "pager": {CONF_TRANSPORT: TRANSPORT_GENERIC, CONF_ACTION: "notify.pager", CONF_INCLUSION: [INCLUSION_DEFAULT]},
        },
    )
    deliveries = ctx.delivery_registry.deliveries

    assert deliveries["phone"].inclusion == [INCLUSION_EXPLICIT]
    assert deliveries["chat"].inclusion == [INCLUSION_EXPLICIT]
    # a delivery's own inclusion still wins
    assert deliveries["pager"].inclusion == [INCLUSION_DEFAULT]
    # and a delivery without its own, left explicit by the setting, isn't reported as having lost it
    assert not any(
        call.kwargs.get("issue_key") == "delivery_lost_implicit_inclusion"
        for call in cast("Mock", ctx.hass_api.raise_issue).call_args_list
    )


async def test_transport_yaml_inclusion_wins_over_default_inclusion() -> None:
    ctx = await _registry(
        "delivery_control:\n  default_inclusion: default\n",
        transports={TRANSPORT_GENERIC: {"delivery_defaults": {CONF_INCLUSION: [INCLUSION_EXPLICIT]}}},
    )
    deliveries = ctx.delivery_registry.deliveries

    assert deliveries["chat"].inclusion == [INCLUSION_EXPLICIT]
    assert deliveries["phone"].inclusion == [INCLUSION_DEFAULT]


async def test_voice_occupancy_for_spoken_deliveries_only() -> None:
    ctx = await _registry(
        "delivery_control:\n  voice_occupancy: only_in\n",
        deliveries={
            **DELIVERIES,
            "announce": {CONF_TRANSPORT: TRANSPORT_TTS, CONF_OCCUPANCY: OCCUPANCY_ANY_IN},
        },
    )
    deliveries = ctx.delivery_registry.deliveries

    assert deliveries["speaker"].occupancy == OCCUPANCY_ONLY_IN
    assert deliveries["announce"].occupancy == OCCUPANCY_ANY_IN
    assert deliveries["chat"].occupancy == OCCUPANCY_ALL
    assert deliveries["phone"].occupancy == OCCUPANCY_ALL


def test_unknown_stored_option_is_dropped() -> None:
    """A Delivery Control option no longer offered, stored by an earlier version, doesn't fail setup"""
    from custom_components.supernotify.schema import CONFIG_ENTRY_SCHEMA

    validated = CONFIG_ENTRY_SCHEMA({"delivery_control": {"default_inclusion": "explicit", "apple_drop_mp4": False}})

    assert validated["delivery_control"] == {"default_inclusion": "explicit"}
