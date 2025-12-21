from typing import TYPE_CHECKING, cast

from homeassistant.core import HomeAssistant

from custom_components.supernotify.notification import Notification
from tests.components.supernotify.doubles_lib import DummyTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from custom_components.supernotify.envelope import Envelope


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
    assert cast("Envelope", uut.deliveries["plain_email"]["delivered_envelopes"][0]).priority == "medium"  # type: ignore

    uut = Notification(ctx, "HIGH RISK!! testing 123")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["high_risk"]
    assert uut.deliveries["plain_email"]["delivered_envelopes"][0].priority == "high"  # type: ignore
    assert uut.deliveries["plain_email"]["delivered_envelopes"][0].message == "testing 123"  # type: ignore

    uut = Notification(ctx, "high risk testing 123")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["high_risk"]
    assert uut.deliveries["plain_email"]["delivered_envelopes"][0].priority == "high"  # type: ignore
    assert uut.deliveries["plain_email"]["delivered_envelopes"][0].message == "testing 123"  # type: ignore

    uut = Notification(ctx, "LOW RISK: testing 123")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["low_risk"]
    assert uut.deliveries["plain_email"]["delivered_envelopes"][0].priority == "low"  # type: ignore
    assert uut.deliveries["plain_email"]["delivered_envelopes"][0].message == "testing 123"  # type: ignore

    uut = Notification(ctx, "UNKNOWN BIRD: small brown flying thing at window")
    await uut.initialize()
    await uut.deliver()
    assert list(uut.enabled_scenarios.keys()) == ["noise"]
    assert "plain_email" not in uut.deliveries
