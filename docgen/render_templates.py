import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

import mkdocs_gen_files
from homeassistant.const import CONF_ACTION
from homeassistant.core import HomeAssistant

sys.path.append(str((Path(__file__).parent / "..").resolve()))
# imports must come after sys.path append
from custom_components.supernotify import CONF_TRANSPORT, PRIORITY_VALUES, TRANSPORT_EMAIL
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from custom_components.supernotify.transports.email import EmailTransport

output_root = "developer/HTML Email Renders"


async def create_examples() -> None:
    hass = HomeAssistant(config_dir=".")
    ctx = TestingContext(
        homeassistant=hass,
        deliveries={"examples": {CONF_TRANSPORT: TRANSPORT_EMAIL, CONF_ACTION: "notify.smtp"}},
        template_path=Path("custom_components/supernotify/default_templates"),
    )
    await ctx.test_initialize()
    uut: EmailTransport = cast("EmailTransport", ctx.transport(TRANSPORT_EMAIL))
    nav = mkdocs_gen_files.Nav()

    logging.debug("Rendering templates for %s", PRIORITY_VALUES)
    try:
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
                logging.warning("No html for template")
                with mkdocs_gen_files.open(f"{output_root}/{dest_page}", "w") as t:
                    t.write("# Example Template Failure\n")
                    t.write("No html generated from examples/templates/default.html.j2")

            else:
                logging.info("Writing %s %s to %s", priority, "default", dest_page)
                with mkdocs_gen_files.open(f"{output_root}/{dest_page}", "w") as t:
                    t.write(html)
                    t.write("\n")

            nav["configuration", "example", "html_email_template", priority] = f"../developer/html_email_renders/{dest_page}"

        logging.debug("Finished template render")
    except Exception as e:
        print(e)  # noqa: T201
        logging.exception("Failed to render templates")


logging.basicConfig()

asyncio.run(create_examples())
