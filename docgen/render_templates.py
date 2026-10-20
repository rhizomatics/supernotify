import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import mkdocs_gen_files
from anyio import Path as AsyncPath
from homeassistant import loader
from homeassistant.const import CONF_ACTION
from homeassistant.core import HomeAssistant

sys.path.append(str((Path(__file__).parent / "..").resolve()))
# imports must come after sys.path append


from custom_components.supernotify.const import CONF_TRANSPORT, PRIORITY_VALUES, TRANSPORT_EMAIL
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from custom_components.supernotify.transports.email import EmailTransport

output_root = "developer/reference/HTML Email Renders"

_LOGGER = logging.getLogger(__name__)


async def create_examples() -> None:
    hass = HomeAssistant(config_dir=".")
    # translations lookup needs the integration loader, which a bare HomeAssistant lacks
    loader.async_setup(hass)
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"examples": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}},
        template_path=AsyncPath("custom_components/supernotify/default_templates"),
    )
    await ctx.test_initialize()
    uut: EmailTransport = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    nav = mkdocs_gen_files.Nav()

    _LOGGER.debug("Rendering templates for %s", PRIORITY_VALUES)
    for priority in PRIORITY_VALUES:
        html = await uut.render_template(
            "default.html.j2",
            Envelope(
                Delivery("test_email", ctx.delivery_config("examples"), uut),
                Notification(ctx, action_data={"priority": priority}),
            ),
            action_data={"message": "Example notification message", "title": "Example notification title"},
            debug_trace=None,
            image_path=None,
            snapshot_url="https://upload.wikimedia.org/wikipedia/commons/a/a5/Information_example_page2_300px.jpg",
            extra_data={},
            strict_template=False,
        )
        dest_page: str = f"example-default-{priority}.md"
        if html is None:
            # fail the docs build rather than publish a placeholder page
            raise RuntimeError(f"No html generated for {priority} example from default.html.j2")

        _LOGGER.info("Writing %s %s to %s", priority, "default", dest_page)
        with mkdocs_gen_files.open(f"{output_root}/{dest_page}", "w") as t:
            t.write(html)
            t.write("\n")

        nav["configuration", "example", "html_email_template", priority] = (
            f"../developer/reference/html_email_renders/{dest_page}"
        )

    _LOGGER.debug("Finished template render")


logging.basicConfig()
# the example renders run against a bare HomeAssistant, which has no URLs or device registry
logging.getLogger("custom_components.supernotify.hass_api").setLevel(logging.ERROR)

asyncio.run(create_examples())
