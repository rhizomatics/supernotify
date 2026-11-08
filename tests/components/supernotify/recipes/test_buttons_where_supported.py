from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import EnvelopeOutcome
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from custom_components.supernotify.transports.pushover import PushoverTransport
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.envelope import Envelope


@pytest.fixture
async def fixture(hass: HomeAssistant):
    """https://supernotify.rhizomatics.org.uk/recipes/buttons_where_supported/"""
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
  pushover:
    transport: pushover
    action: notify.pushover
    inclusion: default
  mobile_push:
    transport: mobile_push
    inclusion: scenario

scenarios:
  needs_buttons:
    alias: Buttons only work on the Companion App
    conditions: "{{ (notification_actions + notification_action_groups) | length > 0 }}"
    delivery:
      pushover:
        enabled: false
      mobile_push:

action_groups:
  garage:
    - action: CLOSE_GARAGE
      title: Close the garage
""",
        services={"notify": ["pushover", "mobile_app_joe_nokia"]},
        viable_transport_types=[MobilePushTransport, PushoverTransport],
    )
    await ctx.test_initialize()
    return ctx


async def test_no_buttons_goes_to_pushover(fixture):
    uut = Notification(fixture, "Garage door left open")
    await uut.initialize()
    await uut.deliver()
    assert uut.selected_scenario_names == []
    assert list(uut.selected_deliveries) == ["pushover"]
    assert len(uut.deliveries["pushover"][EnvelopeOutcome.SUCCESS]) == 1


async def test_action_group_goes_to_mobile_push(fixture):
    uut = Notification(fixture, "Garage door left open", action_data={"action_groups": ["garage"]})
    await uut.initialize()
    await uut.deliver()
    assert uut.selected_scenario_names == ["needs_buttons"]
    assert list(uut.selected_deliveries) == ["mobile_push"]
    envelope: Envelope = uut.deliveries["mobile_push"][EnvelopeOutcome.SUCCESS][0]  # type: ignore
    assert envelope.calls[0].action_data["data"]["actions"] == [  # type: ignore[index]
        {"action": "CLOSE_GARAGE", "title": "Close the garage"}
    ]


async def test_ad_hoc_action_goes_to_mobile_push(fixture):
    uut = Notification(
        fixture, "Garage door left open", action_data={"actions": [{"action": "CLOSE_GARAGE", "title": "Close it now"}]}
    )
    await uut.initialize()
    await uut.deliver()
    assert uut.selected_scenario_names == ["needs_buttons"]
    assert list(uut.selected_deliveries) == ["mobile_push"]
    envelope: Envelope = uut.deliveries["mobile_push"][EnvelopeOutcome.SUCCESS][0]  # type: ignore
    assert {"action": "CLOSE_GARAGE", "title": "Close it now"} in envelope.calls[0].action_data["data"]["actions"]  # type: ignore[index]
