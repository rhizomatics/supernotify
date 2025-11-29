from homeassistant.core import HomeAssistant

from custom_components.supernotify.notification import Notification

from .doubles_lib import DummyTransport
from .hass_setup_lib import TestingContext


async def test_alexa_whispering(hass: HomeAssistant):
    """https://supernotify.rhizomatics.org.uk/recipes/alexa_whisper/"""
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
  name: SuperNotifier
  platform: supernotify
  delivery:
    plain_email:
      transport: email
      action: notify.smtp
    alexa_inform:
      transport: alexa_devices
      target_usage: merge_always
      target:
        entity_id:
          notify.kitchen_alexa_speak
    apple_push:
      transport: mobile_push
  scenarios:
    routine:
        alias: regular low level announcements
        conditions: "{{notification_priority in ['low']}}"
        delivery:
          plain_email:
          apple_push:
          alexa_inform:
            data:
              message_template: '<amazon:effect name="whispered">{{notification_message}}</amazon:effect>'
""",
        services={"notify": ["smtp", "send_message", "kitchen_alexa_speak"]},
    )

    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", action_data={"priority": "low"}, target="joe@soapy.com")
    await uut.initialize()
    await uut.deliver()
    assert len(uut.delivered_envelopes) == 2
    index = {uut.delivered_envelopes[i].delivery_name: i for i in range(0, 2)}
    assert uut.delivered_envelopes[index["plain_email"]].calls[0].action_data["message"] == "testing 123"  # type: ignore
    assert (
        uut.delivered_envelopes[index["alexa_inform"]].calls[0].action_data["message"]  # type: ignore
        == '<amazon:effect name="whispered">testing 123</amazon:effect>'
    )


async def test_home_alone(hass: HomeAssistant):
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
recipients:
    - person: person.joe_mcphee
      email: joe.mcphee@home.mail.net
      phone_number: "+3294924848"
    - person: person.jabilee_sokata
      email: jab@sokata.family.net
delivery:
    apple_push:
      transport: dummy
    alexa_announce:
      transport: dummy
    plain_email:
      transport: dummy
    chimes:
      transport: dummy
      selection: scenario
scenarios:
    lone_night:
        alias: only one person home at night
        conditions:
            condition: and
            conditions:
            - "{{notification_priority not in ['critical','high','low']}}"
            - "{{'LONE_HOME' in occupancy}}"
            - condition: state
              entity_id: alarm_control_panel.home_alarm_control
              state:
              - armed_night
        action_groups:
            - alarm_panel
            - lights
        delivery:
            apple_push:
            alexa_announce:
            plain_email:
            chimes:
""",
        transport_types=[DummyTransport],
        services={"notify": ["send_message"]},
    )
    await ctx.test_initialize()

    ctx.hass.states.async_set("person.joe_mcphee", "home")
    ctx.hass.states.async_set("person.jabilee_sokata", "not_home")
    ctx.hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_night")
    uut = Notification(ctx, "testing 123", action_data={"priority": "medium"}, target="joe@soapy.com")
    await uut.initialize()
    await uut.deliver()
    assert "lone_night" in uut.selected_scenario_names
    assert "chimes" in uut.selected_delivery_names


async def test_minimal_config_parses():
    ctx = TestingContext(
        yaml="""
    name: minimal
    platform: supernotify
    delivery:
      email:
        transport: email
        action: notify.smtp
"""
    )
    await ctx.test_initialize()
    assert ctx.delivery("email") is not None
