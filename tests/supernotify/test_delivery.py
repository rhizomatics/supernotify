from homeassistant.const import (
    CONF_CONDITION,
)
from homeassistant.core import HomeAssistant

from custom_components.supernotify import (
    OCCUPANCY_ALL,
    PRIORITY_VALUES,
    SELECTION_DEFAULT,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.methods.generic import GenericDeliveryMethod
from custom_components.supernotify.methods.notify_entity import NotifyEntityDeliveryMethod
from custom_components.supernotify.model import Target
from custom_components.supernotify.people import PeopleRegistry


def test_target_in_dict_mode() -> None:
    uut = Target({
        "email": ["joe.mctoe@kmail.com"],
        "entity_id": ["media_player.kitchen", "notify.garden"],
        "phone": "+43985951039393",
        "person_id": "person.joe_mctoe",
        "device_id": ["000044449999aaaa00003333ffff7777"],
        "other_id": ["@mctoe"],
        "klaxon": ["dive_dive_dive"],
    })

    assert uut.entity_ids == ["media_player.kitchen", "notify.garden"]
    assert uut.person_ids == ["person.joe_mctoe"]
    assert uut.phone == ["+43985951039393"]
    assert uut.device_ids == ["000044449999aaaa00003333ffff7777"]
    assert uut.email == ["joe.mctoe@kmail.com"]
    assert uut.other_ids == ["@mctoe", "dive_dive_dive"]
    assert uut.label_ids == []
    assert uut.floor_ids == []
    assert uut.area_ids == []


def test_target_in_list_mode() -> None:
    uut = Target([
        "joe.mctoe@kmail.com",
        "media_player.kitchen",
        "+43985951039393",
        "person.joe_mctoe",
        "notify.garden",
        "000044449999aaaa00003333ffff7777",
        "@mctoe",
    ])
    assert uut.entity_ids == ["media_player.kitchen", "notify.garden"]
    assert uut.person_ids == ["person.joe_mctoe"]
    assert uut.phone == ["+43985951039393"]
    assert uut.device_ids == ["000044449999aaaa00003333ffff7777"]
    assert uut.email == ["joe.mctoe@kmail.com"]
    assert uut.other_ids == ["@mctoe"]
    assert uut.label_ids == []
    assert uut.floor_ids == []
    assert uut.area_ids == []


def test_target_in_scalar_mode() -> None:
    assert Target("media_player.kitchen").entity_ids == ["media_player.kitchen"]
    assert Target("000044449999aaaa00003333ffff7777").device_ids == ["000044449999aaaa00003333ffff7777"]
    assert Target("person.joe_mctoe").person_ids == ["person.joe_mctoe"]
    assert Target([]).entity_ids == []


def test_category_access() -> None:
    uut = Target([
        "joe.mctoe@kmail.com",
        "media_player.kitchen",
        "+43985951039393",
        "person.joe_mctoe",
        "notify.garden",
        "000044449999aaaa00003333ffff7777",
        "@mctoe",
    ])
    assert uut.for_category("entity_id") == ["media_player.kitchen", "notify.garden"]
    uut.extend("label_id", "tag1")
    uut.extend("label_id", ["tag1", "tag2"])
    assert uut.for_category("label_id") == ["tag1", "tag2"]
    uut.extend("other_id", "@mctoe2")
    assert uut.for_category("other_id") == ["@mctoe", "@mctoe2"]


async def test_simple_create(mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    uut = Delivery("unit_testing", {}, NotifyEntityDeliveryMethod(mock_hass, mock_context, mock_people_registry, {}))
    assert await uut.validate(mock_context)
    assert uut.name == "unit_testing"
    assert uut.enabled is True
    assert uut.default is False
    assert uut.occupancy == OCCUPANCY_ALL
    assert uut.message is None
    assert uut.title is None
    assert uut.template is None
    assert uut.alias is None
    assert uut.condition is None
    assert uut.priority == PRIORITY_VALUES
    assert uut.selection == [SELECTION_DEFAULT]
    assert uut.method.method == "notify_entity"
    assert uut.data == {}
    assert uut.options == uut.method.default_options
    assert uut.action == "notify.send_message"
    assert uut.target is None


async def test_broken_create_using_reserved_word(mock_hass: HomeAssistant, mock_context: Context) -> None:
    uut = Delivery("ALL", {}, NotifyEntityDeliveryMethod(mock_hass, mock_context, {}))
    assert await uut.validate(mock_context) is False
    mock_context.raise_issue.assert_called_with(  # type: ignore
        "delivery_ALL_reserved_name",
        issue_key="delivery_reserved_name",
        issue_map={"delivery": "ALL"},
    )


async def test_broken_create_with_missing_action(mock_hass: HomeAssistant, mock_context: Context, mock_people_registry) -> None:
    uut = Delivery("generic", {}, GenericDeliveryMethod(mock_hass, mock_context, mock_people_registry, {}))
    assert await uut.validate(mock_context) is False
    mock_context.raise_issue.assert_called_with(  # type: ignore
        "delivery_generic_invalid_action",
        issue_key="delivery_invalid_action",
        issue_map={"action": "", "delivery": "generic"},
    )


async def test_broken_create_with_bad_condition(mock_hass: HomeAssistant, mock_context: Context, mock_people_registry) -> None:
    uut = Delivery(
        "generic",
        {CONF_CONDITION: {"condition": "xor"}},
        GenericDeliveryMethod(mock_hass, mock_context, mock_people_registry, {}),
    )
    assert await uut.validate(mock_context) is False
    mock_context.raise_issue.assert_called_with(  # type: ignore
        "delivery_generic_invalid_condition",
        issue_key="delivery_invalid_condition",
        issue_map={"delivery": "generic", "condition": "{'condition': 'xor'}", "exception": "'integrations'"},
    )
