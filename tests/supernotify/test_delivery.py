from homeassistant.const import (
    CONF_CONDITION,
)
from homeassistant.core import HomeAssistant

from custom_components.supernotify import (
    OCCUPANCY_ALL,
    PRIORITY_VALUES,
    SELECTION_DEFAULT,
)
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.methods.generic import GenericDeliveryMethod
from custom_components.supernotify.methods.notify_entity import NotifyEntityDeliveryMethod


async def test_simple_create(mock_hass: HomeAssistant, mock_context: Context) -> None:
    uut = Delivery("unit_testing", {}, NotifyEntityDeliveryMethod(mock_hass, mock_context, {}))
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
    assert uut.target.entity_id == []


async def test_broken_create_using_reserved_word(mock_hass: HomeAssistant, mock_context: Context) -> None:
    uut = Delivery("ALL", {}, NotifyEntityDeliveryMethod(mock_hass, mock_context, {}))
    assert await uut.validate(mock_context) is False
    mock_context.raise_issue.assert_called_with(  # type: ignore
        "delivery_ALL_reserved_name",
        issue_key="delivery_reserved_name",
        issue_map={"delivery": "ALL"},
    )


async def test_broken_create_with_missing_action(mock_hass: HomeAssistant, mock_context: Context) -> None:
    uut = Delivery("generic", {}, GenericDeliveryMethod(mock_hass, mock_context, {}))
    assert await uut.validate(mock_context) is False
    mock_context.raise_issue.assert_called_with(  # type: ignore
        "delivery_generic_invalid_action",
        issue_key="delivery_invalid_action",
        issue_map={"action": "", "delivery": "generic"},
    )


async def test_broken_create_with_bad_condition(mock_hass: HomeAssistant, mock_context: Context) -> None:
    uut = Delivery("generic", {CONF_CONDITION: {"condition": "xor"}}, GenericDeliveryMethod(mock_hass, mock_context, {}))
    assert await uut.validate(mock_context) is False
    mock_context.raise_issue.assert_called_with(  # type: ignore
        "delivery_generic_invalid_condition",
        issue_key="delivery_invalid_condition",
        issue_map={"delivery": "generic", "condition": "{'condition': 'xor'}", "exception": "'integrations'"},
    )
