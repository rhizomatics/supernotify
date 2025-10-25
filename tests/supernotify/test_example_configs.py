from pathlib import Path

import pytest
from homeassistant.components.notify.const import DOMAIN
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.const import CONF_ENABLED, CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_unordered import unordered

from custom_components.supernotify import CONF_DELIVERY, CONF_NOTIFY, CONF_SELECTION, SELECTION_DEFAULT

EXAMPLES_ROOT = "examples"

examples = [str(p.name) for p in Path(EXAMPLES_ROOT).iterdir()]


@pytest.mark.parametrize("config_name", examples)
async def test_examples(hass: HomeAssistant, config_name: str) -> None:
    config_path: Path = Path(EXAMPLES_ROOT) / config_name
    config = await hass.async_add_executor_job(load_yaml_config_file, str(config_path))

    uut_config = config[CONF_NOTIFY][0]
    service_name = uut_config[CONF_NAME]
    platform = uut_config[CONF_PLATFORM]
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, service_name)
    services = await hass.services.async_call(platform, "enquire_deliveries_by_scenario", blocking=True, return_response=True)
    expected_defaults = [
        d
        for d, dc in uut_config.get(CONF_DELIVERY, {}).items()
        if dc.get(CONF_ENABLED, True) and SELECTION_DEFAULT in dc.get(CONF_SELECTION, [SELECTION_DEFAULT])
    ]
    assert services is not None
    assert services["DEFAULT"] == unordered(expected_defaults)

    await hass.services.async_call(
        DOMAIN,
        service_name,
        {"message": f"unit test - {config_name}", "data": {"delivery": {"testing": None}, "priority": "low"}},
        blocking=True,
    )
    await hass.async_stop()
    await hass.async_block_till_done()
