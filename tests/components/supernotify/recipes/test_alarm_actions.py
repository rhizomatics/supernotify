import pytest
from homeassistant.core import HomeAssistant

from custom_components.supernotify.notification import Notification
from tests.components.supernotify.hass_setup_lib import TestingContext


@pytest.fixture
async def fixture(hass: HomeAssistant):
    """https://supernotify.rhizomatics.org.uk/recipes/alarm_state_actions/"""
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
name: Supernotify
platform: supernotify
recipients:
  - person: person.joe_mcphee
    mobile_devices:
        - mobile_app_id: mobile_app_joe_nokia

delivery:
  apple_push:
    transport: mobile_push
scenarios:
  alarm_disarmed:
    conditions:
      - condition: state
        entity_id: alarm_control_panel.home_alarm
        state:
          - disarmed
    action_groups:
      - alarm_panel_arm
      - alarm_panel_reset

  alarm_armed:
    conditions:
    - condition: state
      entity_id: alarm_control_panel.home_alarm
      state:
        - armed_home
        - armed_night
        - armed_away
    action_groups:
      - alarm_panel_disarm
      - alarm_panel_reset

action_groups:
  alarm_panel_disarm:
    - action: ALARM_PANEL_DISARM
      title: "Disarm Alarm Panel"
      icon: "sfsymbols:bell.slash"
  alarm_panel_reset:
    - action: ALARM_PANEL_RESET
      title: "Arm Alarm Panel for at Home"
      icon: "sfsymbols:bell"
  alarm_panel_arm:
    - action: ALARM_PANEL_AWAY
      title: "Arm Alarm Panel for Going Away"
      icon: "sfsymbols:airplane"
      """,
        services={"notify": ["mobile_app_joe_nokia"]},
    )
    hass.states.async_set("alarm_control_panel.home_alarm", "pending")
    await hass.async_block_till_done()
    await ctx.test_initialize()
    return ctx


async def test_mobile_push_only_has_arm_when_alarm_disarmed(fixture, hass: HomeAssistant):

    hass.states.async_set("alarm_control_panel.home_alarm", "disarmed")
    await hass.async_block_till_done()

    uut = Notification(fixture, "testing 123")
    await uut.initialize()
    await uut.deliver()
    assert uut.selected_scenario_names == ["alarm_disarmed"]
    assert len(uut.delivered_envelopes["mobile_push"]) == 1
    envelope = uut.delivered_envelopes["mobile_push"][0]
    assert envelope.delivery_name == "apple_push"
    assert envelope.calls[0].action_data["data"]["actions"] == [  # type: ignore[index]
        {"action": "ALARM_PANEL_RESET", "title": "Arm Alarm Panel for at Home", "icon": "sfsymbols:bell"},
        {"action": "ALARM_PANEL_AWAY", "title": "Arm Alarm Panel for Going Away", "icon": "sfsymbols:airplane"},
    ]


async def test_mobile_push_only_has_disarm_when_alarm_armed(fixture, hass: HomeAssistant):

    hass.states.async_set("alarm_control_panel.home_alarm", "armed_home")
    await hass.async_block_till_done()

    uut = Notification(fixture, "testing 123")
    await uut.initialize()
    await uut.deliver()
    assert uut.selected_scenario_names == ["alarm_armed"]
    assert len(uut.delivered_envelopes["mobile_push"]) == 1
    envelope = uut.delivered_envelopes["mobile_push"][0]
    assert envelope.delivery_name == "apple_push"
    assert envelope.calls[0].action_data["data"]["actions"] == [  # type: ignore[index]
        {"action": "ALARM_PANEL_DISARM", "title": "Disarm Alarm Panel", "icon": "sfsymbols:bell.slash"},
        {"action": "ALARM_PANEL_RESET", "title": "Arm Alarm Panel for at Home", "icon": "sfsymbols:bell"},
    ]
