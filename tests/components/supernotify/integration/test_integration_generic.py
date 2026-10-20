"""End to end flows through the generic transport, on a real Home Assistant"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from .framework import House

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

CONFIG = """
recipients:
  - person: person.my_user
    delivery:
      slack:
        target:
          slack_channel: A20H2AN55DX
delivery:
  flasher:
    transport: generic
    action: flashywashy.flash_me_now
    options:
      handle_as_domain: light
  announce:
    transport: generic
    action: tts.speak
  dazzle:
    transport: generic
    action: script.turn_on
  modern_notify:
    transport: generic
    action: notify.send_message
  slack:
    transport: generic
    action: notify.my_slack_service
    options:
      target_categories: slack_channel
"""


async def generic_house(hass: HomeAssistant) -> House:
    house = House(
        users={"My User": "my_user"},
        config=CONFIG,
        stub_actions=["flashywashy.flash_me_now", "tts.speak", "notify.my_slack_service"],
    )
    await house.setup(hass)
    return house


async def test_handle_as_domain_targets_handled_domain_entities(hass: HomeAssistant) -> None:
    house = await generic_house(hass)
    try:
        await house.call("""
            message: Intruder
            delivery: flasher
            target: light.kitchen
            data:
              flash: long
        """)
        (call,) = house.service_calls["flashywashy"]
        assert call.data == {"flash": "long", "entity_id": ["light.kitchen"]}
    finally:
        house.cleanup()


async def test_tts_speak_targets_tts_entity_and_media_player(hass: HomeAssistant) -> None:
    house = await generic_house(hass)
    try:
        await house.call("""
            message: Dinner is ready
            delivery: announce
            target:
              - tts.piper
              - media_player.kitchen
        """)
        (call,) = house.service_calls["tts"]
        assert call.service == "speak"
        assert call.data == {
            "message": "Dinner is ready",
            "media_player_entity_id": "media_player.kitchen",
            "entity_id": ["tts.piper"],
        }
    finally:
        house.cleanup()


async def test_script_turn_on_passes_variables_to_script(hass: HomeAssistant) -> None:
    house = await generic_house(hass)
    try:
        assert await async_setup_component(
            hass,
            "script",
            {
                "script": {
                    "dazzle": {
                        "sequence": [{"event": "dazzled", "event_data": {"message": "{{ message }}", "zone": "{{ zone }}"}}]
                    }
                }
            },
        )
        fired: list[Event] = []
        hass.bus.async_listen("dazzled", fired.append)

        await house.call("""
            message: Intruder at the porch
            delivery: dazzle
            target: script.dazzle
            data:
              variables:
                zone: porch
        """)
        await hass.async_block_till_done()

        (event,) = fired
        assert event.data == {"message": "Intruder at the porch", "zone": "porch"}
    finally:
        house.cleanup()


async def test_notify_send_message_targets_entity(hass: HomeAssistant) -> None:
    house = await generic_house(hass)
    try:
        await house.call("""
            message: Bin day
            title: Reminder
            delivery: modern_notify
            target: notify.kitchen_display
        """)
        (call,) = house.service_calls["notify"]
        assert call.service == "send_message"
        assert call.data == {"message": "Bin day", "title": "Reminder", "entity_id": ["notify.kitchen_display"]}
    finally:
        house.cleanup()


async def test_custom_target_category_from_recipient(hass: HomeAssistant) -> None:
    """The documented Slack example, a made-up target category configured on the recipient"""
    house = await generic_house(hass)
    try:
        await house.call("""
            message: Notify via slack
            delivery: slack
            target: person.my_user
        """)
        (call,) = house.service_calls["notify"]
        assert call.service == "my_slack_service"
        assert call.data == {"message": "Notify via slack", "target": "A20H2AN55DX"}
    finally:
        house.cleanup()
