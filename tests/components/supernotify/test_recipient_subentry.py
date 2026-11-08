"""Recipients as config subentries - the subentry flow, the one-off import of YAML recipients,
and the running engine using them"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER, ConfigSubentryData, SubentryFlowResult
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.config_flow import target_from_fields, target_to_fields
from custom_components.supernotify.const import SUBENTRY_TYPE_RECIPIENT
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.repairs import YAML_RECIPIENTS_ISSUE_ID
from custom_components.supernotify.schema import vol
from tests.components.supernotify.ha_testing import MockConfigEntry

from .hass_setup_lib import register_mobile_app, serialize_form

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PHONE_APP = "mobile_app_bobs_phone"
TABLET_APP = "mobile_app_bobs_tablet"
DELIVERY = {"testing": {"transport": "generic", "action": "notify.send_message", "target": ["notify.testy"]}}


async def _entry(
    hass: HomeAssistant, yaml_config: dict[str, Any] | None = None, discovery: bool = False, **kwargs: Any
) -> MockConfigEntry:
    """Recipient discovery is off unless asked for, so only the recipients a test adds are there"""
    entry = MockConfigEntry(domain=DOMAIN, data={"recipients_discovery": discovery}, options={}, **kwargs)
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


@pytest.mark.parametrize(
    "custom",
    [
        "not a target",
        "https://example.com",
        # a known category's value has to pass that category's own check
        "email:not-an-address",
        "phone:not-a-number",
        "mobile_app_id:bobs_phone",
    ],
)
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

    details = {
        "email": "bob@example.com",
        "enabled": True,
        "mobile_discovery": True,
        "mobile_devices": [PHONE_APP],
        "custom_target": ["telegram_chat_id:12345"],
        "delivery_overrides": {"delivery": {"testing": {"enabled": False, "data": {"priority": "high"}}}},
    }
    # the target categories are listed for the custom target field
    assert "telegram_chat_id" in result["description_placeholders"]["categories"]
    # the running deliveries are listed for the delivery field
    assert result["description_placeholders"]["deliveries"] == ", ".join(
        sorted(entry.runtime_data.context.delivery_registry.deliveries)
    )
    result = await _configure(hass, result, details)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    (subentry,) = _recipients(entry)
    assert subentry.unique_id == "person.bob"
    assert dict(subentry.data) == {
        "person": "person.bob",
        # the person's own user, filled in from the person
        "user_id": hass.states.get("person.bob").attributes["user_id"],  # type: ignore[union-attr]
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
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Recipient - Alice"
    await hass.async_block_till_done()

    assert _recipients(entry)[0].unique_id == user.id


async def test_only_users_without_a_person_offered(hass: HomeAssistant) -> None:
    alice = await hass.auth.async_create_user("Alice")
    bob = await hass.auth.async_create_user("Bob")
    hass.states.async_set("person.bob", "home", {"user_id": bob.id})
    entry = await _entry(hass)

    result = await _start(hass, entry)
    assert {o["value"] for o in result["data_schema"].schema["user_id"].config["options"]} == {alice.id}


async def test_no_user_field_when_every_user_has_a_person(hass: HomeAssistant) -> None:
    bob = await hass.auth.async_create_user("Bob")
    hass.states.async_set("person.bob", "home", {"user_id": bob.id})
    entry = await _entry(hass)

    result = await _start(hass, entry)
    assert [str(k) for k in result["data_schema"].schema] == ["person", "alias"]


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


@pytest.mark.parametrize(
    "delivery",
    [
        {"testing": {"data": {"action": "notify.other"}}},
        {"testing": {"colour": "red"}},
        {"testing": {"enabled": "sometimes"}},
        ["testing"],
    ],
)
async def test_invalid_delivery(hass: HomeAssistant, delivery: object) -> None:
    entry = await _entry(hass)
    result = await _configure(hass, await _start(hass, entry), {"person": "person.bob"})
    result = await _configure(
        hass, result, {"enabled": True, "mobile_discovery": True, "delivery_overrides": {"delivery": delivery}}
    )
    assert result["errors"] == {"base": "invalid_delivery"}


async def test_invalid_custom_target(hass: HomeAssistant) -> None:
    entry = await _entry(hass)
    result = await _configure(hass, await _start(hass, entry), {"person": "person.bob"})
    result = await _configure(hass, result, {"enabled": True, "mobile_discovery": True, "custom_target": ["nonsense"]})
    assert result["errors"] == {"custom_target": "invalid_custom_target"}


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
    # every delivery change is there to edit, on the one form
    overrides = result["data_schema"].schema["delivery_overrides"]
    assert not overrides.options["collapsed"]
    (field,) = overrides.schema.schema
    assert field.description["suggested_value"] == {"testing": {"enabled": False, "data": {"priority": "high"}}}

    # emptying the delivery field removes the changes
    details = {"alias": "Bobby", "enabled": True, "mobile_discovery": False, "target": {"entity_id": "notify.kitchen"}}
    result = await _configure(hass, result, details)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert subentry.title == "Recipient - Bobby"
    assert dict(subentry.data) == {
        "person": "person.bob",
        "alias": "Bobby",
        "enabled": True,
        "mobile_discovery": False,
        "target": {"entity_id": ["notify.kitchen"]},
        "mobile_devices": [],
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

    assert sorted((s.unique_id, s.title) for s in _recipients(entry)) == [
        ("abc123", "Recipient - abc123"),
        ("person.bob", "Recipient - Bob"),
    ]
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


async def test_discovered_recipients_listed(hass: HomeAssistant) -> None:
    """Every discovered person gets a subentry, to change or switch off, while one already there is kept"""
    hass.states.async_set("person.alice", "home", {"friendly_name": "Alice"})
    hass.states.async_set("person.bob", "home", {"friendly_name": "Bob"})
    entry = await _entry(
        hass,
        discovery=True,
        subentries_data=[
            ConfigSubentryData(
                data={"person": "person.bob", "enabled": False},
                subentry_type=SUBENTRY_TYPE_RECIPIENT,
                title="Bobby",
                unique_id="person.bob",
            )
        ],
    )

    by_key = {s.unique_id: s for s in _recipients(entry)}
    assert by_key["person.alice"].title == "Recipient - Alice"
    # one titled without the prefix, before it was added, is retitled with it
    assert by_key["person.bob"].title == "Recipient - Bobby"
    assert dict(by_key["person.alice"].data) == {"person": "person.alice"}
    assert dict(by_key["person.bob"].data) == {"person": "person.bob", "enabled": False}
    assert not entry.runtime_data.context.people_registry.people["person.bob"].enabled

    # each recipient's entities are in their subentry, with no device, so a recipient is only
    # listed once in the integration
    entity_registry = er.async_get(hass)
    for entity_id in ("switch.supernotify_recipient_alice", "notify.recipient_alice"):
        registry_entry = entity_registry.async_get(entity_id)
        assert registry_entry is not None
        assert registry_entry.config_subentry_id == by_key["person.alice"].subentry_id
        assert registry_entry.device_id is None
    assert hass.states.get("switch.supernotify_recipient_alice").name == "Recipient Alice Enabled"  # type: ignore[union-attr]
    assert hass.states.get("notify.recipient_alice").name == "Alice"  # type: ignore[union-attr]

    # already listed, so not added again on a reload
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len([s for s in _recipients(entry) if s.unique_id == "person.alice"]) == 1


async def test_add_recipient_who_isnt_a_user(hass: HomeAssistant) -> None:
    entry = await _entry(hass)

    result = await _configure(hass, await _start(hass, entry), {"alias": "Granny Smith"})
    assert result["step_id"] == "details"
    assert result["data_schema"].schema["mobile_devices"].config["options"] == []
    result = await _configure(hass, result, {"email": "granny@example.com", "enabled": True, "mobile_discovery": False})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Recipient - Granny Smith"
    await hass.async_block_till_done()

    (subentry,) = _recipients(entry)
    assert subentry.unique_id == "user.granny_smith"
    recipient = entry.runtime_data.context.people_registry.people["user.granny_smith"]
    assert recipient.email == "granny@example.com"
    assert recipient.target("email").email == ["granny@example.com"]

    # the same name again is the same recipient
    result = await _configure(hass, await _start(hass, entry), {"alias": "Granny Smith"})
    assert result["reason"] == "already_configured"


def _user_recipient(user_id: str, **data: Any) -> ConfigSubentryData:
    return ConfigSubentryData(
        data={"user_id": user_id, "alias": "bob", **data}, subentry_type=SUBENTRY_TYPE_RECIPIENT, title="bob", unique_id=user_id
    )


async def test_user_recipient_becomes_their_persons(hass: HomeAssistant) -> None:
    """Found as a user before being given a Person, then the Person's recipient, keeping what was set"""
    hass.states.async_set("person.bob", "home", {"user_id": "bob-user"})
    entry = await _entry(hass, subentries_data=[_user_recipient("bob-user", email="bob@example.com")])

    (subentry,) = _recipients(entry)
    assert subentry.unique_id == "person.bob"
    assert dict(subentry.data) == {"user_id": "bob-user", "alias": "bob", "email": "bob@example.com", "person": "person.bob"}
    assert list(entry.runtime_data.context.people_registry.people) == ["person.bob"]


async def test_user_recipient_merged_into_persons_already_listed(hass: HomeAssistant) -> None:
    hass.states.async_set("person.bob", "home", {"user_id": "bob-user"})
    person_recipient = ConfigSubentryData(
        data={"person": "person.bob", "enabled": False},
        subentry_type=SUBENTRY_TYPE_RECIPIENT,
        title="Bob",
        unique_id="person.bob",
    )
    entry = await _entry(hass, subentries_data=[_user_recipient("bob-user", email="bob@example.com"), person_recipient])

    (subentry,) = _recipients(entry)
    assert subentry.unique_id == "person.bob"
    # what was set on the Person's recipient wins
    assert dict(subentry.data) == {
        "user_id": "bob-user",
        "alias": "bob",
        "email": "bob@example.com",
        "person": "person.bob",
        "enabled": False,
    }
    assert list(entry.runtime_data.context.people_registry.people) == ["person.bob"]


async def test_form_shows_stored_delivery_overrides(hass: HomeAssistant) -> None:
    """Regression: the delivery overrides section had a default, which the frontend filled it with,
    empty, rather than the overrides stored"""
    overrides = {"testing": {"enabled": False}}
    entry = await _entry(
        hass,
        subentries_data=[
            ConfigSubentryData(
                data={"person": "person.bob", "delivery": overrides},
                subentry_type=SUBENTRY_TYPE_RECIPIENT,
                title="Bob",
                unique_id="person.bob",
            )
        ],
    )
    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=_recipients(entry)[0].subentry_id)
    fields = serialize_form(result["data_schema"])
    section = next(f for f in fields if f["name"] == "delivery_overrides")
    # no default, so the frontend fills it from what's inside
    assert "default" not in section
    assert section["schema"][0]["description"]["suggested_value"] == overrides
