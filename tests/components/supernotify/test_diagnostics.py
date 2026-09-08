"""Tests for diagnostics.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import (
    ATTR_DUPE_POLICY_NONE,
    CONF_DUPE_POLICY,
    CONF_PERSON,
    CONF_PHONE_NUMBER,
    CONF_TRANSPORT,
    TRANSPORT_PERSISTENT,
)
from custom_components.supernotify.diagnostics import async_get_config_entry_diagnostics
from custom_components.supernotify.notify import SupernotifyAction

if TYPE_CHECKING:
    from unittest.mock import Mock

    from homeassistant.core import HomeAssistant

DELIVERY: dict[str, dict] = {"persistent": {CONF_TRANSPORT: TRANSPORT_PERSISTENT}}
RECIPIENTS: list[dict] = [
    {
        CONF_PERSON: "person.new_home_owner",
        "email": "me@tester.net",
        CONF_PHONE_NUMBER: "+2301015050503",
        "user_id": "abc123userid",
        "alias": "Real Name",
    },
]


def _entry(hass: HomeAssistant, service: SupernotifyAction) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    entry.runtime_data = service
    return entry


async def test_diagnostics_redacts_recipient_pii(hass: HomeAssistant, mock_hass: Mock) -> None:
    """Every identifying Recipient field is redacted, non-identifying ones survive untouched.

    recipients_discovery=False keeps this to the single explicitly configured recipient -
    mock_hass.states.async_entity_ids (conftest.py) otherwise feeds two extra auto-discovered
    people into the mix, which is irrelevant to what this test is checking.
    """
    service = SupernotifyAction(mock_hass, deliveries=DELIVERY, recipients=RECIPIENTS, recipients_discovery=False)
    await service.initialize()

    diagnostics = await async_get_config_entry_diagnostics(hass, _entry(hass, service))

    assert diagnostics["counters"] == {"sent": 0, "failures": 0}
    assert len(diagnostics["recipients"]) == 1
    recipient = diagnostics["recipients"][0]
    assert recipient["email"] == "**REDACTED**"
    assert recipient["phone_number"] == "**REDACTED**"
    assert recipient["user_id"] == "**REDACTED**"
    assert recipient["alias"] == "**REDACTED**"
    assert recipient[CONF_PERSON] == "person.new_home_owner"


async def test_diagnostics_no_last_notification_before_any_send(hass: HomeAssistant, mock_hass: Mock) -> None:
    """last_notification is None until something has actually been sent."""
    service = SupernotifyAction(mock_hass, deliveries=DELIVERY, recipients=[], recipients_discovery=False)
    await service.initialize()

    diagnostics = await async_get_config_entry_diagnostics(hass, _entry(hass, service))

    assert diagnostics["last_notification"] is None


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_diagnostics_includes_last_notification(hass: HomeAssistant, mock_hass: Mock) -> None:
    """Once a message has been sent, its contents (in diagnostics mode) are included.

    Pre-existing quirk, unrelated to diagnostics.py itself: Notification.contents(diagnostics=
    True) -> common.sanitize() walks every attribute of a real Notification built against
    mock_hass, and at least one of those turns out to be an AsyncMock exposing its own
    auto-generated `.contents` attribute - sanitize() calls it like the real thing, producing
    a coroutine nothing awaits. Doesn't happen against a real HomeAssistant instance.
    """
    service = SupernotifyAction(
        mock_hass,
        deliveries=DELIVERY,
        recipients=[],
        recipients_discovery=False,
        dupe_check={CONF_DUPE_POLICY: ATTR_DUPE_POLICY_NONE},
    )
    await service.initialize()
    # explicit delivery selection keeps this to the one transport/delivery under test, rather
    # than also triggering the auto-generated implicit deliveries (mobile_push, notify_entity)
    # that a plain async_send_message would also fan out to
    await service.async_send_message(message="hello", title="test", data={"delivery": ["persistent"]})

    diagnostics = await async_get_config_entry_diagnostics(hass, _entry(hass, service))

    assert diagnostics["last_notification"] is not None
    assert diagnostics["last_notification"]["message"] == "hello"
