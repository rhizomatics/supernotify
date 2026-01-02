import datetime as dt

import pytest
from homeassistant.core import HomeAssistant

from custom_components.supernotify.notification import Notification
from custom_components.supernotify.transports.chime import ChimeTransport
from tests.components.supernotify.hass_setup_lib import TestingContext, register_device


@pytest.fixture
async def recipe_fixture(hass: HomeAssistant):
    ctx = TestingContext(
        homeassistant=hass,
        yaml="""
transport:
  notify_entity:
    disabled: true
  chime:
    delivery_defaults:
      options:
        chime_aliases:
          doorbell:
            alexa_devices: amzn_sfx_doorbell_chime_02
          xmas_doorbell:
            alexa_devices: christmas_05
          car_on_driveway:
            alexa_devices: amzn_sfx_trumpet_bugle_04
delivery:
  doorbell_rang:
    transport: chime
    selection: explicit
    data:
      chime_tune: doorbell
  driveway_alarm:
    transport: chime
    selection: explicit
    data:
      chime_tune: car_on_driveway
scenarios:
    xmas:
      alias: Christmas season
      conditions:
        condition: or
        conditions:
          - "{{ (12,24) <= (now().month, now().day) <= (12,31) }}"
          - "{{ (1,1) <= (now().month, now().day) <= (1,1) }}"
      delivery:
        doorbell_rang:
          enabled:
          data:
            chime_tune: xmas_doorbell
""",
        transport_types=[ChimeTransport],
        services={"alexa_devices": ["send_sound"]},
    )
    register_device(
        ctx.hass_api,
        device_id="00001111222233334444555566667777",
        domain="alexa_devices",
        domain_id="test_01",
        title="test fixture",
    )
    await ctx.test_initialize()
    return ctx


@pytest.mark.freeze_time(dt.datetime(2024, 12, 25, 11, tzinfo=dt.UTC))
async def test_seasonal_scenario_on_xmas_day(recipe_fixture):

    uut = Notification(recipe_fixture, "testing 123", action_data={"delivery": "doorbell_rang"})
    await uut.initialize()
    await uut.deliver()

    assert len(uut.deliveries["doorbell_rang"]["delivered"]) == 1
    assert len(uut.deliveries["doorbell_rang"]["delivered"][0].calls) == 1  # type:ignore
    call = uut.deliveries["doorbell_rang"]["delivered"][0].calls[0]  # type:ignore
    assert call.action == "send_sound"
    assert call.domain == "alexa_devices"
    assert call.action_data["sound"] == "christmas_05"  # type:ignore


@pytest.mark.freeze_time(dt.datetime(2024, 12, 25, 11, tzinfo=dt.UTC))
async def test_unseasonal_scenario_on_xmas_day(recipe_fixture):

    uut = Notification(recipe_fixture, "testing 123", action_data={"delivery": "driveway_alarm"})
    await uut.initialize()
    await uut.deliver()

    assert len(uut.deliveries["driveway_alarm"]["delivered"]) == 1
    assert len(uut.deliveries["driveway_alarm"]["delivered"][0].calls) == 1  # type:ignore
    call = uut.deliveries["driveway_alarm"]["delivered"][0].calls[0]  # type:ignore
    assert call.action == "send_sound"
    assert call.domain == "alexa_devices"
    assert call.action_data["sound"] == "amzn_sfx_trumpet_bugle_04"  # type:ignore


@pytest.mark.freeze_time(dt.datetime(2024, 6, 25, 11, tzinfo=dt.UTC))
async def test_seasonal_scenario_in_summer(recipe_fixture):

    uut = Notification(recipe_fixture, "testing 123", action_data={"delivery": "doorbell_rang"})
    await uut.initialize()
    await uut.deliver()

    assert len(uut.deliveries["doorbell_rang"]["delivered"]) == 1
    assert len(uut.deliveries["doorbell_rang"]["delivered"][0].calls) == 1  # type:ignore
    call = uut.deliveries["doorbell_rang"]["delivered"][0].calls[0]  # type:ignore
    assert call.action == "send_sound"
    assert call.domain == "alexa_devices"
    assert call.action_data["sound"] == "amzn_sfx_doorbell_chime_02"  # type:ignore
