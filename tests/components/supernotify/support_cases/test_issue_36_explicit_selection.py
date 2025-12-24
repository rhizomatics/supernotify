import pytest
from homeassistant.core import HomeAssistant
from pytest_unordered import unordered

from custom_components.supernotify.notification import Notification
from tests.components.supernotify.hass_setup_lib import TestingContext, register_mobile_app


@pytest.fixture
async def support_case_fixture(hass: HomeAssistant):
    """https://github.com/rhizomatics/supernotify/issues/36"""
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
    name: Supernotify
    platform: supernotify
    delivery:
      signal:
        transport: generic
        action: notify.signal
        options:
          target_categories: phone_number
        selection:
          - explicit
          - fallback
    recipients:
      - person: person.foo
        phone_number: "+121290012345"
        delivery:
# default to discovered mobile apps, plus:
          signal: {}
      - person: person.bar
        phone_number: "+121290067890"
        delivery:
           signal:
             enabled: true

""",
        services={"notify": ["signal"], "mobile_app": ["iphone"]},
    )
    register_mobile_app(ctx.hass_api, person="person.foo", device_name="foophone", title="Foo Phone")
    await ctx.test_initialize()
    return ctx


async def test_mobile_push_only_when_no_explicit_delivery(support_case_fixture, hass: HomeAssistant):

    uut = Notification(support_case_fixture, "testing 123")
    await uut.initialize()
    await uut.deliver()

    assert list(uut.deliveries.keys()) == unordered("signal", "DEFAULT_mobile_push", "DEFAULT_notify_entity")
    assert len(uut.deliveries["DEFAULT_mobile_push"]["delivered"]) == 1
    assert len(uut.deliveries["signal"]["delivered"]) == 1
    assert len(uut.deliveries["DEFAULT_notify_entity"].get("delivered", [])) == 0


async def test_explicit_delivery_and_mobile_and_explicit_selection(support_case_fixture, hass: HomeAssistant):

    uut = Notification(support_case_fixture, "testing 123", action_data={"delivery": "signal"})
    await uut.initialize()
    await uut.deliver()

    assert list(uut.deliveries.keys()) == ["signal"]
    assert len(uut.deliveries["signal"]["delivered"]) == 1


async def test_explicit_delivery_and_mobile_and_implicit_selection(support_case_fixture, hass: HomeAssistant):

    uut = Notification(support_case_fixture, "testing 123", action_data={"delivery": {"signal": {}}})
    await uut.initialize()
    await uut.deliver()

    assert list(uut.deliveries.keys()) == unordered("signal", "DEFAULT_mobile_push", "DEFAULT_notify_entity")
    assert len(uut.deliveries["signal"]["delivered"]) == 1
    assert len(uut.deliveries["DEFAULT_mobile_push"]["delivered"]) == 1
    assert len(uut.deliveries["DEFAULT_notify_entity"].get("delivered", [])) == 0


async def test_explicit_delivery_no_mobile(support_case_fixture, hass: HomeAssistant):

    uut = Notification(support_case_fixture, "testing 123", target="person.bar")
    await uut.initialize()
    await uut.deliver()

    assert list(uut.deliveries.keys()) == unordered("signal", "DEFAULT_mobile_push", "DEFAULT_notify_entity")
    assert len(uut.deliveries["signal"]["delivered"]) == 1
    assert len(uut.deliveries["DEFAULT_mobile_push"].get("delivered", [])) == 0
    assert len(uut.deliveries["DEFAULT_notify_entity"].get("delivered", [])) == 0
