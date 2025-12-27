import pytest
from homeassistant.core import HomeAssistant

from custom_components.supernotify.notification import Notification
from tests.components.supernotify.hass_setup_lib import TestingContext


@pytest.fixture
async def support_case_fixture(hass: HomeAssistant):
    """https://github.com/rhizomatics/supernotify/issues/36"""
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
    name: Supernotify
    platform: supernotify
    delivery:
      tts:
        transport: generic
        action: tts.cloud_say
        options:
          data_keys_exclude_re: title
    transport:
      notify_entity:
        enabled: false
      mobile_push:
        enabled: false
""",
        services={"tts": ["cloud_say"]},
    )
    await ctx.test_initialize()
    return ctx


async def test_title_not_passed_to_action(support_case_fixture, hass: HomeAssistant):

    uut = Notification(support_case_fixture, "testing 123")
    await uut.initialize()
    await uut.deliver()

    assert list(uut.deliveries.keys()) == ["tts"]
    envelope = uut.deliveries["tts"]["delivered"][0]  # type: ignore
    service_call = envelope.calls[0]  # type: ignore
    assert service_call.action_data == {"message": "testing 123"}
    assert service_call.domain == 'tts'
