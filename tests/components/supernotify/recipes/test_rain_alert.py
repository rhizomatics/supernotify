from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import parse_yaml
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.supernotify import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall


async def test_rain_alert(hass: HomeAssistant) -> None:
    """https://supernotify.rhizomatics.org.uk/recipes/rain_alert/"""
    pushed: list[ServiceCall] = []
    chatted: list[ServiceCall] = []

    async def _push(call: ServiceCall) -> None:
        pushed.append(call)

    async def _chat(call: ServiceCall) -> None:
        chatted.append(call)

    # another delivery every notification usually goes to, which the scenario switches off
    hass.services.async_register("testing", "chat", _chat)
    # a phone with the Home Assistant app, so there is a standard mobile_push delivery
    MockConfigEntry(domain="mobile_app", data={"device_name": "Joes Phone"}).add_to_hass(hass)
    hass.services.async_register("notify", "mobile_app_joes_phone", _push)
    hass.states.async_set("person.joe", "home")
    hass.states.async_set("binary_sensor.rain", "off")
    config = parse_yaml("""
supernotify:
  recipients:
    - person: person.joe
      mobile_devices:
        - mobile_app_id: mobile_app_joes_phone
  delivery:
    family_chat:
      transport: generic
      action: testing.chat
      target_required: never
      inclusion: default
  scenarios:
    rain:
      alias: Its raining again
      notify_entity: its_raining_again
      delivery:
        mobile_push:
          data:
            priority: low
            notification_icon: mdi:weather-pouring
        .*:
          enabled: false

alert:
  rain:
    name: Its raining again
    entity_id: binary_sensor.rain
    repeat: 60
    notifiers:
      - its_raining_again
""")
    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, "alert", config)
    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.rain", "on")
    await hass.async_block_till_done()

    assert [dict(c.data) for c in pushed] == [
        {
            "message": "Its raining again",
            "data": {"notification_icon": "mdi:weather-pouring", "push": {"interruption-level": "passive"}},
        }
    ]
    assert chatted == []
