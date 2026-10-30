"""End to end flows through the kodi, discord, persistent and pushover transports, on a real Home Assistant"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .framework import House

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CONFIG = """
delivery:
  discord_alerts:
    transport: discord
    action: notify.discord
  pushover_home:
    transport: pushover
    action: notify.pushover_home
    inclusion: explicit
  popup:
    transport: persistent
    inclusion: explicit
"""

STUB_ACTIONS = ["notify.discord", "notify.pushover_home", "kodi.call_method", "persistent_notification.create"]


async def native_house(hass: HomeAssistant) -> House:
    MockConfigEntry(domain="kodi", data={}).add_to_hass(hass)
    lounge = er.async_get(hass).async_get_or_create("media_player", "kodi", "lounge_id", suggested_object_id="kodi_lounge")
    hass.states.async_set(lounge.entity_id, "idle")
    for action in STUB_ACTIONS:
        domain, service = action.split(".", 1)
        hass.services.async_register(domain, service, AsyncMock())
    house = House(users={"Bob": "bob"}, config=CONFIG, stub_actions=STUB_ACTIONS)
    await house.setup(hass)
    return house


def calls(house: House, domain: str, service: str) -> list[ServiceCall]:
    return [c for c in house.service_calls.get(domain, []) if c.service == service]


async def test_kodi_overlay_for_critical_notification(hass: HomeAssistant) -> None:
    house = await native_house(hass)
    try:
        await house.call("""
            message: Door open
            priority: critical
            target: media_player.kodi_lounge
            delivery:
              kodi:
                data:
                  kodi_displaytime: 500
        """)
        (overlay,) = calls(house, "kodi", "call_method")
        assert overlay.data["method"] == "GUI.ShowNotification"
        assert overlay.data["image"] == "error"
        assert overlay.data["displaytime"] == 1500
        assert overlay.data["entity_id"] == ["media_player.kodi_lounge"]
    finally:
        house.cleanup()


async def test_discord_selected_by_qualified_channel_target(hass: HomeAssistant) -> None:
    house = await native_house(hass)
    try:
        await house.call("""
            message: Motion
            title: Garden
            target:
              - discord_channel:123456789012345678
        """)
        (post,) = calls(house, "notify", "discord")
        assert post.data == {"message": "**Garden**\nMotion", "target": ["123456789012345678"]}
    finally:
        house.cleanup()


async def test_pushover_emergency_sends_devices_as_target(hass: HomeAssistant) -> None:
    house = await native_house(hass)
    try:
        await house.call("""
            message: Flood
            priority: critical
            delivery:
              pushover_home:
                data:
                  pushover_device: iphone
                  pushover_tags: flood
                  pushover_callback: https://ha.example/api/webhook/ack
        """)
        (push,) = calls(house, "notify", "pushover_home")
        assert push.data["target"] == ["iphone"]
        assert push.data["data"] == {
            "priority": 2,
            "retry": 60,
            "expire": 3600,
            "callback_url": "https://ha.example/api/webhook/ack",
            "tags": ["flood"],
        }
    finally:
        house.cleanup()


async def test_persistent_notification_id_from_data(hass: HomeAssistant) -> None:
    house = await native_house(hass)
    try:
        await house.call("""
            message: Washing done
            data:
              notification_id: laundry
            delivery:
              popup: {}
        """)
        (popup,) = calls(house, "persistent_notification", "create")
        assert popup.data == {"message": "Washing done", "notification_id": "laundry"}
    finally:
        house.cleanup()
