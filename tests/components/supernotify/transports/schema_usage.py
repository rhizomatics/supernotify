"""Check the action calls a transport makes against the schema of the integration receiving them

Each transport's tests have a `test_schema_usage`, which delivers once with nothing but a message,
and once with everything the transport can make use of, and validates every resulting action call.

The schema is the one the downstream integration registers with Home Assistant:

- For the core entity domains, like `notify` or `media_player`, the domain is set up and the
  schema read back from the action registry.
- Integrations that need a config entry before registering actions have their schema imported.
  Several of those can't be imported without their own third party library, which isn't a
  dependency here, so that library is stubbed out for long enough to import the schema.
- Legacy notify platforms, including the custom integrations, all register `NOTIFY_SERVICE_SCHEMA`
  and interpret `data` in their own code, so that is as far as their calls can be validated.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.notify.const import NOTIFY_SERVICE_SCHEMA
from homeassistant.setup import async_setup_component

from custom_components.supernotify.compat import vol
from custom_components.supernotify.const import (
    ATTR_ACTIONS,
    ATTR_MEDIA,
    ATTR_PRIORITY,
    CONF_TRANSPORT,
    PRIORITY_CRITICAL,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.target import Target
from tests.components.supernotify.hass_setup_lib import TestingContext

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.transport import Transport

SNAPSHOT = Path("/media/supernotify/snapshot.jpg")

# notification wide extras that any transport might draw on for its largest call
MAXIMAL_ACTION_DATA: dict[str, Any] = {
    ATTR_PRIORITY: PRIORITY_CRITICAL,
    ATTR_MEDIA: {"snapshot_url": "https://my.home/snaps/porch.jpg", "clip_url": "https://my.home/clips/porch.mp4"},
    ATTR_ACTIONS: [{"action": "URI", "title": "Open Camera", "url": "https://my.home/cameras/porch"}],
}

# where integrations that only register actions once they have a config entry keep the schema
IMPORTED_SCHEMAS: dict[tuple[str, str], tuple[str, str]] = {
    ("alexa_devices", "send_sound"): ("alexa_devices.services", "SCHEMA_SOUND_SERVICE"),
    ("html5", "send_message"): ("html5.services", "SERVICE_SEND_MESSAGE_SCHEMA"),
    ("kodi", "call_method"): ("kodi.services", "KODI_CALL_METHOD_SCHEMA"),
    ("lametric", "chart"): ("lametric.services", "SERVICE_CHART_SCHEMA"),
    ("lametric", "message"): ("lametric.services", "SERVICE_MESSAGE_SCHEMA"),
    ("matrix", "send_message"): ("matrix.services", "SERVICE_SCHEMA_SEND_MESSAGE"),
    ("mqtt", "publish"): ("mqtt", "MQTT_PUBLISH_SCHEMA"),
    ("ntfy", "publish"): ("ntfy.services", "SERVICE_PUBLISH_SCHEMA"),
    ("telegram_bot", "send_document"): ("telegram_bot.services", "SERVICE_SCHEMA_SEND_FILE"),
    ("telegram_bot", "send_message"): ("telegram_bot.services", "SERVICE_SCHEMA_SEND_MESSAGE"),
    ("telegram_bot", "send_photo"): ("telegram_bot.services", "SERVICE_SCHEMA_SEND_FILE"),
}

# actions defined by the user rather than by an integration, so with no schema to check
SCHEMALESS_DOMAINS = {"rest_command"}

sizes = pytest.mark.parametrize("maximal", [False, True], ids=["minimal", "maximal"])


@dataclass
class SchemaCase:
    transport: type[Transport]
    targets: Any = None
    expected: set[str] = field(default_factory=set)  # actions that must be called
    delivery: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)  # data needed for any call at all
    maximal_data: dict[str, Any] = field(default_factory=dict)
    image: bool = False  # an image is available even for the minimal call
    context: dict[str, Any] = field(default_factory=dict)  # extra TestingContext arguments


def _import_schema(module: str, name: str) -> Any:  # ruff: ignore[any-type]
    """Import a schema, stubbing out any third party library the integration needs but isn't installed

    Older Home Assistant versions keep some of these schemas elsewhere, or build them in a way
    that a stubbed library can't stand in for, and the test is skipped for those.
    """
    while True:
        try:
            return getattr(importlib.import_module(f"homeassistant.components.{module}"), name)
        except ModuleNotFoundError as e:
            if not e.name or e.name.startswith("homeassistant."):
                pytest.skip(f"No {module}.{name} schema in this Home Assistant version: {e}")
            sys.modules[e.name] = MagicMock()
        except AttributeError as e:
            pytest.skip(f"No {module}.{name} schema in this Home Assistant version: {e}")


async def downstream_schema(hass: HomeAssistant, domain: str, service: str) -> Any | None:  # ruff: ignore[any-type]
    """Schema for an action, or None where there is nothing to validate against"""
    if domain in SCHEMALESS_DOMAINS:
        return None
    if (domain, service) in IMPORTED_SCHEMAS:
        return _import_schema(*IMPORTED_SCHEMAS[domain, service])
    if domain == "notify" and service != "send_message":
        return NOTIFY_SERVICE_SCHEMA
    assert await async_setup_component(hass, domain, {})
    return hass.services.async_services_internal()[domain][service].schema


async def deliver(case: SchemaCase, maximal: bool) -> list[tuple[str, dict[str, Any], dict[str, Any] | None]]:
    """Deliver through the transport and return each action call as (action, data, target)"""
    ctx = TestingContext(
        deliveries={"uut": {CONF_TRANSPORT: case.transport.name, **case.delivery}},
        viable_transport_types=[case.transport],
        **case.context,
    )
    await ctx.test_initialize()
    uut = ctx.transport(case.transport.name)
    notification = Notification(
        ctx,
        message="Motion at the porch, see https://my.home/cameras/porch",
        title="Porch Alert" if maximal else None,
        action_data=dict(MAXIMAL_ACTION_DATA) if maximal else None,
    )
    await notification.initialize()
    envelope = Envelope(
        Delivery("uut", ctx.delivery_config("uut"), uut),
        notification,
        target=Target(case.targets) if case.targets else None,
        data={**case.data, **(case.maximal_data if maximal else {})},
    )
    # the image can't be fetched for real
    with patch.object(Envelope, "grab_image", AsyncMock(return_value=SNAPSHOT if maximal or case.image else None)):
        assert await uut.deliver(envelope)
    return [
        (f"{call.args[0]}.{call.args[1]}", call.kwargs["service_data"], call.kwargs["target"])
        for call in ctx.hass.services.async_call.call_args_list  # type: ignore[attr-defined]
    ]


async def assert_schema_usage(hass: HomeAssistant, case: SchemaCase, maximal: bool) -> None:
    calls = await deliver(case, maximal)

    assert case.expected <= {action for action, _data, _target in calls}
    if maximal and case.maximal_data:
        # guard against a maximal case that the transport quietly ignores
        assert calls != await deliver(case, maximal=False)
    for action, service_data, target in calls:
        domain, service = action.split(".", 1)
        schema = await downstream_schema(hass, domain, service)
        if schema is None:
            continue
        try:
            # as Home Assistant does, with the target merged into the data
            schema({**(service_data or {}), **(target or {})})
        except vol.Invalid as e:
            raise AssertionError(f"{action} rejects data={service_data} target={target}: {e}") from e
