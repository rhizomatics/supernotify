from typing import TYPE_CHECKING, cast

from homeassistant.core import HomeAssistant
from pytest_unordered import unordered

from custom_components.supernotify.notification import Notification
from tests.components.supernotify.doubles_lib import DummyTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope


async def test_content_escalation_by_delivery_selection(hass: HomeAssistant):
    ctx = TestingContext(
        homeassistant=hass,
        transports={"notify_entity": {"enabled": False}},
        deliveries="""
        plain_email:
          transport: email
          action: notify.smtp
          target: joey@mctest.com
          selection: scenario
        sms:
          transport: sms
          action: notify.4g_modem
          target: "+4394889348934"
          selection: scenario
        apple_push:
          transport: mobile_push
          target: mobile_app_iphone
        """,
        scenarios="""
    high_alert:
        alias: make a fuss if alarm armed or high priority
        conditions:
          - "{{notification_priority in ['high'] and 'person was detected' in notification_message|lower }}"
          - condition: state
            entity_id: alarm_control_panel.home_alarm_control
            state:
              - armed_away
              - armed_vacation
        delivery:
          .*:
            enabled: true
            data:
              priority: critical
""",
        services={"notify": ["send_message", "smtp", "4g_modem", "mobile_app_iphone"]},
    )
    await ctx.test_initialize()
    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_away")

    uut: Notification = Notification(ctx, "person was detected at back door")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == []
    assert list(uut.selected_deliveries) == ["apple_push"]
    assert cast("Envelope", uut.deliveries["apple_push"]["delivered"][0]).priority == "medium"  # type: ignore

    uut = Notification(ctx, "person was detected at back door", action_data={"priority": "high"})
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["high_alert"]
    assert list(uut.selected_deliveries) == unordered("plain_email", "apple_push", "sms")
    assert cast("Envelope", uut.deliveries["plain_email"]["delivered"][0]).priority == "critical"  # type: ignore


async def test_content_escalation_by_priority(hass: HomeAssistant):
    ctx = TestingContext(
        homeassistant=hass,
        deliveries="""
         plain_email:
          transport: dummy
          target: joey@mctest.com
        """,
        scenarios="""
          high_risk:
            conditions: "{{notification_message is match('HIGH RISK',ignorecase=True) }}"
            delivery:
              plain_email:
                data:
                  priority: high
                  message_template: "{{notification_message | regex_replace('high risk[:!]*','',ignorecase=True) | trim}}"
          low_risk:
            conditions: "{{notification_message is match('LOW RISK',ignorecase=True)}}"
            delivery:
              plain_email:
                data:
                  priority: low
                  message_template: "{{notification_message | regex_replace('low risk[:!]*','',ignorecase=True) | trim}}"
          noise:
            conditions: "{{notification_message is match('UNKNOWN BIRD',ignorecase=True)}}"
            delivery:
              plain_email:
                enabled: false
""",
        transport_types=[DummyTransport],
        services={"notify": ["send_message"]},
    )
    await ctx.test_initialize()

    uut: Notification = Notification(ctx, "testing 123")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == []
    assert cast("Envelope", uut.deliveries["plain_email"]["delivered"][0]).priority == "medium"  # type: ignore

    uut = Notification(ctx, "HIGH RISK!! testing 123")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["high_risk"]
    # type: ignore
    assert uut.deliveries["plain_email"]["delivered"][0].priority == "high"  # type: ignore
    # type: ignore
    assert uut.deliveries["plain_email"]["delivered"][0].message == "testing 123"  # type: ignore

    uut = Notification(ctx, "high risk testing 123")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["high_risk"]
    # type: ignore
    assert uut.deliveries["plain_email"]["delivered"][0].priority == "high"  # type: ignore
    # type: ignore
    assert uut.deliveries["plain_email"]["delivered"][0].message == "testing 123"  # type: ignore

    uut = Notification(ctx, "LOW RISK: testing 123")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["low_risk"]

    assert uut.deliveries["plain_email"]["delivered"][0].priority == "low"  # type: ignore

    assert uut.deliveries["plain_email"]["delivered"][0].message == "testing 123"  # type: ignore

    uut = Notification(ctx, "UNKNOWN BIRD: small brown flying thing at window")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["noise"]
    assert "plain_email" not in uut.deliveries
