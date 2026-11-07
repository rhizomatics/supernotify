"""Recipients as config subentries - the subentry flow, the one-off import of YAML recipients,
and the running engine using them"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER, ConfigSubentryData, SubentryFlowResult
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.config_flow import target_from_fields, target_to_fields
from custom_components.supernotify.const import SUBENTRY_TYPE_RECIPIENT
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.repairs import YAML_RECIPIENTS_ISSUE_ID
from custom_components.supernotify.schema import vol

from .hass_setup_lib import register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PHONE_APP = "mobile_app_bobs_phone"
TABLET_APP = "mobile_app_bobs_tablet"
DELIVERY = {"testing": {"transport": "generic", "action": "notify.send_message", "target": ["notify.testy"]}}


async def _entry(hass: HomeAssistant, yaml_config: dict[str, Any] | None = None, **kwargs: Any) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={}, **kwargs)
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: yaml_config or {"delivery": DELIVERY}})
    await hass.async_block_till_done()
    return entry


def _recipients(entry: MockConfigEntry) -> list[Any]:
    return [s for s in entry.subentries.values() if s.subentry_type == SUBENTRY_TYPE_RECIPIENT]


async def _start(
    hass: HomeAssistant, entry: MockConfigEntry, source: str = SOURCE_USER, subentry_id: str | None = None
) -> SubentryFlowResult:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_RECIPIENT),
        context={"source": source, "subentry_id": subentry_id} if subentry_id else {"source": source},
    )


async def _configure(
    hass: HomeAssistant, result: SubentryFlowResult, user_input: dict[str, Any] | None = None
) -> SubentryFlowResult:
    return await hass.config_entries.subentries.async_configure(result["flow_id"], user_input or {})


def test_target_fields_round_trip() -> None:
    target = target_from_fields(
        {"entity_id": "notify.kitchen", "area_id": ["lounge"]},
        ["bob@example.com", "+447700900123", "telegram_chat_id:12345", "slack:C123", " "],
    )
    assert target == {
        "entity_id": ["notify.kitchen"],
        "area_id": ["lounge"],
        "email": ["bob@example.com"],
        "phone": ["+447700900123"],
        "telegram_chat_id": ["12345"],
        "slack": ["C123"],
    }
    selected, custom = target_to_fields(target)
    assert target_from_fields(selected, custom) == target


@pytest.mark.parametrize("custom", ["not a target", "https://example.com"])
def test_target_fields_reject_unrecognised_custom_target(custom: str) -> None:
    with pytest.raises(vol.Invalid):
        target_from_fields(None, [custom])


async def test_add_recipient(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    register_mobile_app(hass_api, person="person.bob", device_name="Bobs Phone")
    register_mobile_app(hass_api, person="person.bob", device_name="Bobs Tablet")
    entry = await _entry(hass)

    result = await _start(hass, entry)
    assert result["step_id"] == "user"
    result = await _configure(hass, result, {"person": "person.bob"})
    assert result["step_id"] == "details"
    assert {o["value"] for o in result["data_schema"].schema["mobile_devices"].config["options"]} == {PHONE_APP, TABLET_APP}

    result = await _configure(
        hass,
        result,
        {
            "email": "bob@example.com",
            "enabled": True,
            "mobile_discovery": True,
            "mobile_devices": [PHONE_APP],
            "custom_target": ["telegram_chat_id:12345"],
        },
    )
    assert result["type"] == FlowResultType.MENU
    assert result["menu_options"] == ["delivery", "save"]

    result = await _configure(hass, result, {"next_step_id": "delivery"})
    result = await _configure(hass, result, {"delivery": "testing"})
    assert result["step_id"] == "delivery_override"
    result = await _configure(hass, result, {"enabled": "disabled", "extra_data": {"priority": "high"}})
    assert result["type"] == FlowResultType.MENU
    result = await _configure(hass, result, {"next_step_id": "save"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = _recipients(entry)
    assert subentry.unique_id == "person.bob"
    assert dict(subentry.data) == {
        "person": "person.bob",
        "email": "bob@example.com",
        "enabled": True,
        "mobile_discovery": True,
        "target": {"telegram_chat_id": ["12345"]},
        "mobile_devices": [
            {"mobile_app_id": PHONE_APP, "enabled": True},
            {"mobile_app_id": TABLET_APP, "enabled": False},
        ],
        "delivery": {"testing": {"enabled": False, "data": {"priority": "high"}}},
    }
    # the entry reloads, and the running engine has the recipient as configured
    recipient = entry.runtime_data.context.people_registry.people["person.bob"]
    assert recipient.email == "bob@example.com"
    assert list(recipient.enabled_mobile_devices) == [PHONE_APP]
    assert recipient.disabling_delivery_names() == ["testing"]


async def test_add_user_only_recipient(hass: HomeAssistant) -> None:
    user = await hass.auth.async_create_user("Alice")
    entry = await _entry(hass)

    result = await _start(hass, entry)
    assert {o["value"] for o in result["data_schema"].schema["user_id"].config["options"]} == {user.id}
    result = await _configure(hass, result, {"user_id": user.id})
    result = await _configure(hass, result, {"alias": "Alice", "enabled": True, "mobile_discovery": True})
    result = await _configure(hass, result, {"next_step_id": "save"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Alice"
    await hass.async_block_till_done()

    assert _recipients(entry)[0].unique_id == user.id


async def test_person_or_user_required(hass: HomeAssistant) -> None:
    entry = await _entry(hass)
    result = await _configure(hass, await _start(hass, entry), {})
    assert result["errors"] == {"base": "person_or_user_required"}


async def test_already_a_recipient(hass: HomeAssistant) -> None:
    entry = await _entry(
        hass,
        subentries_data=[
            ConfigSubentryData(
                data={"person": "person.bob"}, subentry_type=SUBENTRY_TYPE_RECIPIENT, title="Bob", unique_id="person.bob"
            )
        ],
    )
    result = await _configure(hass, await _start(hass, entry), {"person": "person.bob"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_custom_target_and_extra_data(hass: HomeAssistant) -> None:
    entry = await _entry(hass)
    result = await _configure(hass, await _start(hass, entry), {"person": "person.bob"})
    result = await _configure(hass, result, {"enabled": True, "mobile_discovery": True, "custom_target": ["nonsense"]})
    assert result["errors"] == {"custom_target": "invalid_custom_target"}

    result = await _configure(hass, result, {"enabled": True, "mobile_discovery": True})
    result = await _configure(hass, result, {"next_step_id": "delivery"})
    result = await _configure(hass, result, {"delivery": "testing"})
    result = await _configure(hass, result, {"enabled": "default", "extra_data": {"action": "notify.other"}})
    assert result["errors"] == {"extra_data": "invalid_extra_data"}


async def test_reconfigure_recipient(hass: HomeAssistant) -> None:
    entry = await _entry(
        hass,
        subentries_data=[
            ConfigSubentryData(
                data={
                    "person": "person.bob",
                    "email": "bob@example.com",
                    "target": {"entity_id": ["notify.kitchen"], "telegram_chat_id": ["12345"]},
                    "delivery": {"testing": {"enabled": False, "data": {"priority": "high"}}},
                },
                subentry_type=SUBENTRY_TYPE_RECIPIENT,
                title="person.bob",
                unique_id="person.bob",
            )
        ],
    )
    (subentry,) = _recipients(entry)

    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=subentry.subentry_id)
    assert result["step_id"] == "details"
    suggested = {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}
    assert suggested["email"] == "bob@example.com"
    assert suggested["target"] == {"entity_id": ["notify.kitchen"]}
    assert suggested["custom_target"] == ["telegram_chat_id:12345"]

    result = await _configure(
        hass, result, {"alias": "Bobby", "enabled": True, "mobile_discovery": False, "target": {"entity_id": "notify.kitchen"}}
    )
    # emptying a delivery override removes it
    result = await _configure(hass, result, {"next_step_id": "delivery"})
    result = await _configure(hass, result, {"delivery": "testing"})
    suggested = {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}
    assert suggested["enabled"] == "disabled"
    assert suggested["extra_data"] == {"priority": "high"}
    result = await _configure(hass, result, {"enabled": "default"})
    result = await _configure(hass, result, {"next_step_id": "save"})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert subentry.title == "Bobby"
    assert dict(subentry.data) == {
        "person": "person.bob",
        "alias": "Bobby",
        "enabled": True,
        "mobile_discovery": False,
        "target": {"entity_id": ["notify.kitchen"]},
        "mobile_devices": [],
        "delivery": {},
    }
    assert entry.runtime_data.context.people_registry.people["person.bob"].alias == "Bobby"


async def test_yaml_recipients_imported_once_with_repair(hass: HomeAssistant) -> None:
    yaml_config = {
        "delivery": DELIVERY,
        "recipients": [
            {"person": "person.bob", "alias": "Bob", "email": "bob@example.com"},
            {"user_id": "abc123", "phone_number": "+447700900123"},
        ],
    }
    entry = await _entry(hass, yaml_config)

    assert sorted((s.unique_id, s.title) for s in _recipients(entry)) == [("abc123", "abc123"), ("person.bob", "Bob")]
    assert entry.runtime_data.context.people_registry.people["person.bob"].email == "bob@example.com"
    assert ir.async_get(hass).async_get_issue(DOMAIN, YAML_RECIPIENTS_ISSUE_ID) is not None

    # changed in the UI, the subentry wins over the YAML still there
    bob = next(s for s in _recipients(entry) if s.unique_id == "person.bob")
    hass.config_entries.async_update_subentry(entry, bob, data={**bob.data, "email": "robert@example.com"})
    await hass.async_block_till_done()

    assert len(_recipients(entry)) == 2
    assert entry.runtime_data.context.people_registry.people["person.bob"].email == "robert@example.com"


async def test_no_repair_without_yaml_recipients(hass: HomeAssistant) -> None:
    entry = await _entry(hass)
    assert not _recipients(entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, YAML_RECIPIENTS_ISSUE_ID) is None
