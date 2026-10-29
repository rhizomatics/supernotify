"""End to end flows through the sms, mqtt, html5 and telegram transports, on a real Home Assistant"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .framework import House

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CONFIG = """
recipients:
  - person: person.bob
    phone_number: "+447979123456"
delivery:
  sms:
    transport: sms
    action: notify.smsify
"""

STUB_ACTIONS = ["notify.smsify", "mqtt.publish", "html5.send_message", "telegram_bot.send_message"]


async def messaging_house(hass: HomeAssistant) -> House:
    MockConfigEntry(domain="mqtt", data={}).add_to_hass(hass)
    MockConfigEntry(domain="html5", data={}).add_to_hass(hass)
    MockConfigEntry(domain="telegram_bot", data={}).add_to_hass(hass)
    entity_registry = er.async_get(hass)
    browser = entity_registry.async_get_or_create("notify", "html5", "chrome_id", suggested_object_id="chrome")
    hass.states.async_set(browser.entity_id, "unknown")
    chat = entity_registry.async_get_or_create("notify", "telegram_bot", "family_id", suggested_object_id="family_chat")
    hass.states.async_set(chat.entity_id, "unknown")
    # registered ahead of setup, so the transports are viable - House replaces them with recording stubs
    for action in STUB_ACTIONS:
        domain, service = action.split(".", 1)
        hass.services.async_register(domain, service, AsyncMock())
    house = House(users={"Bob": "bob"}, config=CONFIG, stub_actions=STUB_ACTIONS)
    await house.setup(hass)
    return house


def calls(house: House, domain: str, service: str) -> list[ServiceCall]:
    return [c for c in house.service_calls.get(domain, []) if c.service == service]


async def test_sms_to_recipient_keeps_currency_and_brackets(hass: HomeAssistant) -> None:
    house = await messaging_house(hass)
    try:
        await house.call("""
            message: "\U0001f6a8 Bill £20 (due today)"
            target: person.bob
        """)
        (sms,) = calls(house, "notify", "smsify")
        assert sms.data == {"message": " Bill £20 (due today)", "target": ["+447979123456"]}
    finally:
        house.cleanup()


async def test_mqtt_topic_target_publishes_without_other_deliveries_data(hass: HomeAssistant) -> None:
    house = await messaging_house(hass)
    try:
        await house.call("""
            message: Siren on
            target: topic:zigbee2mqtt/siren/set
            data:
              clickAction: /lovelace/security
            delivery:
              mqtt:
                data:
                  payload: "ON"
                  retain: true
        """)
        (publish,) = calls(house, "mqtt", "publish")
        assert publish.data == {"topic": "zigbee2mqtt/siren/set", "payload": "ON", "retain": True}
    finally:
        house.cleanup()


async def test_html5_selected_for_its_own_notify_entity(hass: HomeAssistant) -> None:
    house = await messaging_house(hass)
    try:
        await house.call("""
            message: Door open
            target: notify.chrome
        """)
        (push,) = calls(house, "html5", "send_message")
        assert push.data["entity_id"] == ["notify.chrome"]
        assert push.data["message"] == "Door open"
        assert push.data["title"] == "Notification"
        assert push.data["lang"] == "en"
        # html5 claims its own entities ahead of the generic notify_entity transport
        assert not calls(house, "notify", "send_message")
    finally:
        house.cleanup()


async def test_telegram_sends_to_every_chat_without_other_deliveries_data(hass: HomeAssistant) -> None:
    house = await messaging_house(hass)
    try:
        await house.call("""
            message: Door open
            target:
              - telegram_chat_id:215678938
              - telegram_chat_id:-987654321
            data:
              clickAction: /lovelace/security
        """)
        (send,) = calls(house, "telegram_bot", "send_message")
        assert send.data == {"chat_id": [215678938, -987654321], "message": "Door open", "parse_mode": "plain_text"}
    finally:
        house.cleanup()


async def test_telegram_selected_for_its_own_notify_entity(hass: HomeAssistant) -> None:
    house = await messaging_house(hass)
    try:
        await house.call("""
            message: Door open
            target: notify.family_chat
        """)
        (send,) = calls(house, "telegram_bot", "send_message")
        assert send.data["entity_id"] == ["notify.family_chat"]
        # telegram claims its own entities ahead of the generic notify_entity transport
        assert not calls(house, "notify", "send_message")
    finally:
        house.cleanup()
