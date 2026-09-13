from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

import pytest
from anyio import Path
from homeassistant.components.notify.const import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.const import CONF_ENABLED
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import (
    CONF_DELIVERY,
    CONF_INCLUSION,
    CONF_NOTIFY,
    CONF_TRANSPORT,
    INCLUSION_DEFAULT,
    INCLUSION_EXPLICIT,
    TRANSPORT_ALEXA,
    TRANSPORT_EMAIL,
    TRANSPORT_HTML5,
    TRANSPORT_MOBILE_PUSH,
    TRANSPORT_NOTIFY_ENTITY,
    TRANSPORT_SMS,
)
from custom_components.supernotify.repairs import ISSUE_ID

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

EXAMPLES_ROOT = "examples"

examples = [str(p.name) for p in pathlib.Path(EXAMPLES_ROOT).iterdir() if p.name.endswith(".yaml")]

# Deliberately still in the old `notify: - platform: supernotify` shape - the repairs.py
# migration fixture. Should only exercise the legacy shim (notify.py's async_get_service), not
# a real service.
LEGACY_SHAPE_EXAMPLES = {"unmigrated.yaml"}

# transports whose Transport.inclusion_mode defaults to INCLUSION_DEFAULT - a delivery for
# one of these that doesn't set its own `inclusion:` inherits that, everything else inherits
# INCLUSION_EXPLICIT (see Transport.inclusion_mode/Delivery.initialize's repair warning)
DEFAULT_INCLUSION_TRANSPORTS = {
    TRANSPORT_EMAIL,
    TRANSPORT_ALEXA,
    TRANSPORT_MOBILE_PUSH,
    TRANSPORT_NOTIFY_ENTITY,
    TRANSPORT_SMS,
    TRANSPORT_HTML5,
}


@pytest.mark.parametrize("config_name", examples)
async def test_example_yaml_config(hass: HomeAssistant, config_name: str) -> None:
    if config_name == "minimal.yaml":
        # no longer any minimal necessary config with UI ConfigFlow
        return
    config_path: Path = Path(EXAMPLES_ROOT) / config_name
    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_home")
    # a typical house has at least one notify entity (e.g. a companion app), so
    # notify_entity's auto_configure (gated on the "notify" domain having an entity)
    # behaves the same as it would in a real house
    hass.states.async_set("notify.mock_notify_target", "unknown")
    config = await hass.async_add_executor_job(load_yaml_config_file, str(config_path))

    if config_name in LEGACY_SHAPE_EXAMPLES:
        await _assert_legacy_shape_raises_repair(hass, config)
        return

    uut_config = config[DOMAIN]
    service_name = "supernotify"
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.services.has_service(NOTIFY_DOMAIN, service_name)
    deliveries = await hass.services.async_call(DOMAIN, "enquire_implicit_deliveries", blocking=True, return_response=True)
    expected_defaults: dict[str, list[str]] = {
        TRANSPORT_NOTIFY_ENTITY: ["notify_entity"],
        TRANSPORT_MOBILE_PUSH: ["mobile_push"],
    }
    optional_defaults: dict[str, list[str]] = {}

    expected: dict[str, list[str]] = {}
    configured: dict[str, list[str]] = {}
    for d, dc in uut_config.get(CONF_DELIVERY, {}).items():
        if dc.get(CONF_ENABLED, True):
            configured.setdefault(dc[CONF_TRANSPORT], [])
            configured[dc[CONF_TRANSPORT]].append(d)
            inherited_inclusion = (
                [INCLUSION_DEFAULT] if dc[CONF_TRANSPORT] in DEFAULT_INCLUSION_TRANSPORTS else [INCLUSION_EXPLICIT]
            )
            if INCLUSION_DEFAULT in dc.get(CONF_INCLUSION, inherited_inclusion):
                expected.setdefault(dc[CONF_TRANSPORT], [])
                expected[dc[CONF_TRANSPORT]].append(d)
    for tname, tdef in expected_defaults.items():
        if tname not in configured:
            expected.setdefault(tname, tdef)
    for tname, tdef in optional_defaults.items():
        if tname in deliveries:
            expected.setdefault(tname, tdef)

    assert deliveries is not None
    assert deliveries == expected

    recipients = deliveries = await hass.services.async_call(DOMAIN, "enquire_recipients", blocking=True, return_response=True)
    assert recipients is not None
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        service_name,
        {"message": f"unit test - {config_name}", "data": {"delivery": {"testing": None}, "priority": "low"}},
        blocking=True,
    )
    await hass.async_stop()
    await hass.async_block_till_done()


async def _assert_legacy_shape_raises_repair(hass: HomeAssistant, config: dict) -> None:
    """A leftover `notify: - platform: supernotify` block is inert on its own - the legacy shim
    (notify.py's async_get_service) declines to register anything from it and raises the
    legacy_yaml_config repair instead (a real notify.supernotify still exists, from the
    always-bootstrapped, empty-until-configured config entry - see repairs.py for the actual
    migration flow that would carry this fixture's deliveries/etc across)."""
    assert config.get(CONF_NOTIFY), f"expected a legacy notify: block in this fixture, got {list(config.keys())}"
    assert await async_setup_component(hass, NOTIFY_DOMAIN, config)
    await hass.async_block_till_done()

    issue_registry = ir.async_get(hass)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is not None
