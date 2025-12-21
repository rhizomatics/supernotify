from homeassistant.core import HomeAssistant

from custom_components.supernotify.notification import Notification
from tests.components.supernotify.doubles_lib import DummyTransport
from tests.components.supernotify.hass_setup_lib import TestingContext


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
