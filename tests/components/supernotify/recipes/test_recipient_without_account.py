"""https://supernotify.rhizomatics.org.uk/recipes/recipient_without_account/

A recipient added by name in the integration, with an e-mail address and a Telegram chat id,
notified by their recipient id or their notify entity"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import SUBENTRY_TYPE_RECIPIENT
from tests.components.supernotify.ha_testing import MockConfigEntry
from tests.components.supernotify.integration.framework import House

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CONFIG = """
delivery:
  email:
    transport: email
    action: notify.smtp
"""
STUB_ACTIONS = ["notify.smtp", "telegram_bot.send_message"]


async def granny_house(hass: HomeAssistant) -> House:
    MockConfigEntry(domain="telegram_bot", data={}).add_to_hass(hass)
    # registered ahead of setup, so the transports are viable - House replaces them with recording stubs
    for action in STUB_ACTIONS:
        domain, service = action.split(".", 1)
        hass.services.async_register(domain, service, AsyncMock())
    # the real notify.send_message, to reach the recipient's notify entity
    house = House(users={"Bob": "bob"}, config=CONFIG, stub_actions=STUB_ACTIONS, alexa_per_area=False, stub_send_message=False)
    await house.setup(hass)

    # Settings -> Devices & services -> Supernotify -> Add recipient
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_RECIPIENT), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"alias": "Granny Smith"})
    assert result["step_id"] == "details"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "email": "granny@example.com",
            "custom_target": ["telegram_chat_id:215678938"],
            "enabled": True,
            "mobile_discovery": False,
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY, result.get("errors")
    await hass.async_block_till_done()
    return house


def calls(house: House, domain: str, service: str) -> list[ServiceCall]:
    return [c for c in house.service_calls.get(domain, []) if c.service == service]


async def test_recipient_by_id_gets_email_and_telegram(hass: HomeAssistant) -> None:
    house = await granny_house(hass)
    try:
        await house.call("""
            title: Sunday lunch
            message: Roast at 1pm
            target: user.granny_smith
        """)
        (email,) = calls(house, "notify", "smtp")
        assert email.data["target"] == ["granny@example.com"]
        (telegram,) = calls(house, "telegram_bot", "send_message")
        assert telegram.data["chat_id"] == [215678938]
    finally:
        house.cleanup()


@pytest.mark.parametrize(
    ("service", "data"),
    [
        # the recipient's notify entity
        ("send_message", {"entity_id": "notify.recipient_granny_smith"}),
        # the action of the same name, for anything taking only a notify action's name
        ("recipient_granny_smith", {}),
    ],
)
async def test_recipient_notify_entity_gets_email_and_telegram(hass: HomeAssistant, service: str, data: dict[str, str]) -> None:
    house = await granny_house(hass)
    try:
        await hass.services.async_call(
            "notify", service, {**data, "title": "Sunday lunch", "message": "Roast at 1pm"}, blocking=True
        )
        await hass.async_block_till_done()
        (email,) = calls(house, "notify", "smtp")
        assert email.data["target"] == ["granny@example.com"]
        (telegram,) = calls(house, "telegram_bot", "send_message")
        assert telegram.data["chat_id"] == [215678938]
    finally:
        house.cleanup()


async def test_everyone_includes_recipient(hass: HomeAssistant) -> None:
    house = await granny_house(hass)
    try:
        await house.call("""
            message: Power cut expected tomorrow
        """)
        (email,) = calls(house, "notify", "smtp")
        assert "granny@example.com" in email.data["target"]
        (telegram,) = calls(house, "telegram_bot", "send_message")
        assert telegram.data["chat_id"] == [215678938]
    finally:
        house.cleanup()
