import pathlib

from anyio import Path
from bs4 import BeautifulSoup
from homeassistant.const import CONF_ACTION, CONF_OPTIONS
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.supernotify.const import (
    CONF_TEMPLATE,
    CONF_TRANSPORT,
    OPTION_STRICT_TEMPLATE,
    TRANSPORT_EMAIL,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification

from .hass_setup_lib import TestingContext


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
        template_path=pathlib.Path("custom_components/supernotify/default_templates"),
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
