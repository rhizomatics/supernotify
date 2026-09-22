from __future__ import annotations

import importlib.util
from contextlib import ExitStack
from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.setup import async_setup_component

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def smtp_config_flow() -> bool:
    """Whether the installed HA version sets up smtp notify via a config entry import
    flow (and so a direct SMTP connection can be reused from it), rather than as a
    legacy discovered notify platform with no config entry to reuse."""
    return importlib.util.find_spec("homeassistant.components.smtp.config_flow") is not None


async def setup_smtp(hass: HomeAssistant, extra_config: dict | None = None) -> None:
    config = {
        **(extra_config or {}),
        "notify": [
            {
                "name": "mailservice",
                "platform": "smtp",
                "server": "localhost",
                "encryption": "none",
                "sender": "hass@localhost.org",
                "recipient": ["tester@localhost.org"],
            },
        ],
    }
    if extra_config:
        assert await async_setup_component(hass, next(iter(extra_config)), config)

    with ExitStack() as stack:
        if smtp_config_flow():
            # HA >= 2026.x: smtp notify is set up via a config entry import flow
            stack.enter_context(patch("homeassistant.components.smtp.config_flow.validate_input", return_value={}))
            stack.enter_context(patch("homeassistant.components.smtp.helpers.SmtpClient.connect"))
        else:
            # older HA: smtp notify is a legacy discovered notify platform
            stack.enter_context(patch("homeassistant.components.smtp.notify.MailNotificationService.connection_is_valid"))
        assert await async_setup_component(hass, "notify", config)
        await hass.async_block_till_done()
    await hass.async_block_till_done()
