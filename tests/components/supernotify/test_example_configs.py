import pathlib

import pytest
from anyio import Path
from bs4 import BeautifulSoup
from homeassistant.components.notify.const import DOMAIN
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.const import CONF_ACTION, CONF_ENABLED, CONF_NAME, CONF_OPTIONS, CONF_PLATFORM
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from custom_components.supernotify import (
    CONF_DELIVERY,
    CONF_NOTIFY,
    CONF_SELECTION,
    CONF_TEMPLATE,
    CONF_TRANSPORT,
    OPTION_STRICT_TEMPLATE,
    SELECTION_DEFAULT,
    TRANSPORT_EMAIL,
    TRANSPORT_MOBILE_PUSH,
    TRANSPORT_NOTIFY_ENTITY,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification

from .hass_setup_lib import TestingContext

EXAMPLES_ROOT = "examples"

examples = [str(p.name) for p in pathlib.Path(EXAMPLES_ROOT).iterdir() if p.name.endswith(".yaml")]


@pytest.mark.parametrize("config_name", examples)
async def test_example_yaml_config(hass: HomeAssistant, config_name: str) -> None:
    config_path: Path = Path(EXAMPLES_ROOT) / config_name
    hass.states.async_set("alarm_control_panel.home_alarm_control", "armed_home")
    config = await hass.async_add_executor_job(load_yaml_config_file, str(config_path))

    uut_config = config[CONF_NOTIFY][0]
    service_name = uut_config[CONF_NAME]
    platform = uut_config[CONF_PLATFORM]
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, service_name)
    deliveries = await hass.services.async_call(platform, "enquire_implicit_deliveries", blocking=True, return_response=True)
    expected_defaults: dict[str, list[str]] = {
        TRANSPORT_NOTIFY_ENTITY: ["DEFAULT_notify_entity"],
        TRANSPORT_MOBILE_PUSH: ["DEFAULT_mobile_push"],
    }

    expected: dict[str, list[str]] = {}
    configured: dict[str, list[str]] = {}
    for d, dc in uut_config.get(CONF_DELIVERY, {}).items():
        if dc.get(CONF_ENABLED, True):
            configured.setdefault(dc[CONF_TRANSPORT], [])
            configured[dc[CONF_TRANSPORT]].append(d)
            if SELECTION_DEFAULT in dc.get(CONF_SELECTION, [SELECTION_DEFAULT]):
                expected.setdefault(dc[CONF_TRANSPORT], [])
                expected[dc[CONF_TRANSPORT]].append(d)
    for tname, tdef in expected_defaults.items():
        if tname not in configured:
            expected.setdefault(tname, tdef)

    assert deliveries is not None
    assert deliveries == expected

    recipients = deliveries = await hass.services.async_call(
        platform, "enquire_recipients", blocking=True, return_response=True
    )
    assert recipients is not None
    await hass.services.async_call(
        DOMAIN,
        service_name,
        {"message": f"unit test - {config_name}", "data": {"delivery": {"testing": None}, "priority": "low"}},
        blocking=True,
    )
    await hass.async_stop()
    await hass.async_block_till_done()


async def test_example_template_strict_parsed(hass: HomeAssistant) -> None:
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={
            "test_email": {
                CONF_TRANSPORT: TRANSPORT_EMAIL,
                CONF_ACTION: "notify.smtp",
                CONF_TEMPLATE: "default.html.j2",
                CONF_OPTIONS: {OPTION_STRICT_TEMPLATE: True},
            }
        },
        template_path=pathlib.Path("examples/templates"),
        services={"notify": ["smtp"]},
    )
    await ctx.test_initialize()
    uut = ctx.transport(TRANSPORT_EMAIL)

    await uut.deliver(
        Envelope(
            Delivery("test_email", ctx.delivery_config("test_email"), uut),
            Notification(
                ctx,
                message="hello there",
                title="testing",
            ),
            target=Target(["tester9@assert.com"]),
            data={
                "media": {"snapshot_url": "http://127.0.0.1/hallway/snapshot"},
                "action_url": "http://127.0.0.1/alert/detail",
                "action_url_title": "Event Detail",
            },
        ),
    )
    await ctx.hass.async_block_till_done()
    assert uut.error_count == 0
    assert len(ctx.services["notify.smtp"].calls) == 1
    service_call: ServiceCall = ctx.services["notify.smtp"].calls[0]
    html: str = service_call.data["data"]["html"]
    assert "{%" not in html
    assert "{{" not in html
    parsed = BeautifulSoup(html, "html.parser")
    assert parsed.find("p", class_="alert_message").get_text() == "hello there"  # type: ignore
    assert parsed.find("a", class_="alert_action").get_text() == "Event Detail"  # type: ignore
    assert "None" not in html

    artefact_path: Path = Path("site/tests/results")
    await artefact_path.mkdir(parents=True, exist_ok=True)
    async with await (artefact_path / "email_template.html").open("w") as f:
        await f.write(html)
