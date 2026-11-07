"""Transports as config subentries - those in use listed, the subentry flow for adding and
changing one, the one-off import of YAML transports, and the running engine using them"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER, ConfigSubentryData, SubentryFlowResult
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import SUBENTRY_TYPE_TRANSPORT
from custom_components.supernotify.repairs import YAML_TRANSPORTS_ISSUE_ID
from custom_components.supernotify.schema import TRANSPORT_SCHEMA, as_raw_config

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

DELIVERY = {"testing": {"transport": "generic", "action": "notify.send_message", "target": ["notify.testy"]}}
GENERIC = {
    "load": True,
    "delivery_defaults": {
        "action": "notify.send_message",
        "priority": ["high"],
        "conditions": [{"condition": "template", "value_template": "{{ true }}"}],
    },
}


async def _entry(hass: HomeAssistant, yaml_config: dict[str, Any] | None = None, **kwargs: Any) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={"recipients_discovery": False}, options={}, **kwargs)
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"delivery": DELIVERY} if yaml_config is None else yaml_config})
    await hass.async_block_till_done()
    return entry


def _transports(entry: MockConfigEntry) -> dict[str, Any]:
    return {
        s.unique_id: s
        for s in entry.subentries.values()
        if s.subentry_type == SUBENTRY_TYPE_TRANSPORT and s.unique_id is not None
    }


def _generic_subentry() -> ConfigSubentryData:
    return ConfigSubentryData(data=GENERIC, subentry_type=SUBENTRY_TYPE_TRANSPORT, title="generic", unique_id="generic")


async def _start(
    hass: HomeAssistant, entry: MockConfigEntry, source: str = SOURCE_USER, subentry_id: str | None = None
) -> SubentryFlowResult:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_TRANSPORT),
        context={"source": source, "subentry_id": subentry_id} if subentry_id else {"source": source},
    )


async def _configure(hass: HomeAssistant, result: SubentryFlowResult, user_input: dict[str, Any]) -> SubentryFlowResult:
    return await hass.config_entries.subentries.async_configure(result["flow_id"], user_input)


def _suggested(result: SubentryFlowResult) -> dict[str, Any]:
    return {str(k): k.description["suggested_value"] for k in result["data_schema"].schema if k.description}


def _section(result: SubentryFlowResult, name: str) -> Any:  # ruff: ignore[any-type]
    return result["data_schema"].schema[name]


def _section_suggested(section: Any) -> dict[str, Any]:  # ruff: ignore[any-type]
    return {
        str(k): k.description["suggested_value"]
        for k in section.schema.schema
        if k.description and k.description.get("suggested_value") is not None
    }


async def test_transports_in_use_listed(hass: HomeAssistant) -> None:
    entry = await _entry(hass)

    transports = _transports(entry)
    assert {"generic", "persistent"} <= set(transports)
    assert dict(transports["generic"].data) == {}
    assert transports["generic"].title == "generic"
    # the transport's switch is in its subentry, with no device, so it's only listed once
    registry_entry = er.async_get(hass).async_get("switch.supernotify_transport_generic")
    assert registry_entry is not None
    assert registry_entry.config_subentry_id == transports["generic"].subentry_id
    assert registry_entry.device_id is None

    # already listed, so not added again on a reload
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len([s for s in entry.subentries.values() if s.unique_id == "generic"]) == 1


async def test_add_transport(hass: HomeAssistant) -> None:
    entry = await _entry(hass, {})
    assert "generic" not in _transports(entry)

    result = await _start(hass, entry)
    assert result["step_id"] == "user"
    addable = result["data_schema"].schema["transport"].config["options"]
    # not those listed already, nor those whose integration isn't here
    assert "generic" in addable
    assert "chime" in addable
    assert "persistent" not in addable
    assert "telegram" not in addable

    result = await _configure(hass, result, {"transport": "generic"})
    assert result["step_id"] == "details"
    assert result["description_placeholders"]["learn_more_url"].endswith("/transports/generic/")
    # generic's action is configured, so it has a field for it, with the other delivery defaults
    assert "action" in _section(result, "delivery_defaults").schema.schema
    result = await _configure(
        hass,
        result,
        {
            "enabled": True,
            "advanced": {"load": True},
            "delivery_defaults": {
                "action": "notify.send_message",
                "target": {"entity_id": ["notify.testy"]},
                "data": {"priority": "high"},
            },
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY, result.get("errors")
    await hass.async_block_till_done()

    subentry = _transports(entry)["generic"]
    assert dict(subentry.data) == {
        "enabled": True,
        "load": True,
        "delivery_defaults": {
            "action": "notify.send_message",
            "data": {"priority": "high"},
            "target": {"entity_id": ["notify.testy"]},
        },
    }
    # the entry reloads, and now has generic's own delivery, from its action
    delivery = entry.runtime_data.context.delivery_registry.deliveries["generic"]
    assert delivery.action == "notify.send_message"


async def test_no_transports_to_add(hass: HomeAssistant) -> None:
    entry = await _entry(hass)
    with patch("custom_components.supernotify.static_config.TRANSPORTS", []):
        result = await _start(hass, entry)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "no_transports"


async def test_fields_only_where_the_transport_has_them(hass: HomeAssistant) -> None:
    entry = await _entry(hass)
    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=_transports(entry)["persistent"].subentry_id)
    assert result["step_id"] == "details"
    assert "action" not in _section(result, "delivery_defaults").schema.schema
    # and the connection only for a transport that makes its own, like email
    assert "connection" not in result["data_schema"].schema


async def test_reconfigure_transport(hass: HomeAssistant) -> None:
    entry = await _entry(hass, subentries_data=[_generic_subentry()])
    subentry = _transports(entry)["generic"]

    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=subentry.subentry_id)
    assert result["step_id"] == "details"
    advanced = _section(result, "advanced")
    # collapsed, as it's loaded
    assert advanced.options["collapsed"]
    assert _section_suggested(advanced)["load"] is True
    defaults = _section(result, "delivery_defaults")
    assert not defaults.options["collapsed"]
    suggested = _section_suggested(defaults)
    assert suggested["action"] == "notify.send_message"
    assert suggested["priority"] == ["high"]
    assert suggested["debug"] is False
    # debug first, and target usage just above the targets it's about
    fields = [str(k) for k in defaults.schema.schema]
    assert fields[0] == "debug"
    assert fields.index("target_usage") == fields.index("target") - 1
    # what has no field of its own is in the other delivery defaults
    assert suggested["other_delivery_defaults"] == {"conditions": GENERIC["delivery_defaults"]["conditions"]}

    result = await _configure(
        hass,
        result,
        {
            "enabled": False,
            "advanced": {"load": True},
            "alias": "Chat",
            "delivery_defaults": {
                "action": "notify.send_message",
                "target_usage": "fixed",
                "priority": ["high"],
                "other_delivery_defaults": suggested["other_delivery_defaults"],
            },
        },
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert subentry.title == "Chat"
    assert dict(subentry.data) == {
        **GENERIC,
        "enabled": False,
        "alias": "Chat",
        "delivery_defaults": {**GENERIC["delivery_defaults"], "target_usage": "fixed"},  # type: ignore
    }
    assert entry.runtime_data.context.delivery_registry.transports["generic"].enabled is False


async def test_not_loaded(hass: HomeAssistant) -> None:
    """Load off leaves the transport out entirely, while it stays listed to turn back on"""
    entry = await _entry(hass, subentries_data=[_generic_subentry()])
    subentry = _transports(entry)["generic"]
    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=subentry.subentry_id)
    result = await _configure(
        hass, result, {"enabled": True, "advanced": {"load": False}, "delivery_defaults": {"action": "notify.send_message"}}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert subentry.data["load"] is False
    assert "generic" not in entry.runtime_data.context.delivery_registry.transports
    assert "generic" in _transports(entry)


async def test_connection(hass: HomeAssistant) -> None:
    email = ConfigSubentryData(
        data={"connection": {"host": "smtp.example.com", "username": "postie", "password": "secret"}},
        subentry_type=SUBENTRY_TYPE_TRANSPORT,
        title="email",
        unique_id="email",
    )
    entry = await _entry(hass, subentries_data=[email])
    subentry = _transports(entry)["email"]

    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=subentry.subentry_id)
    connection = _section(result, "connection")
    # first, where there is one
    assert [str(k) for k in result["data_schema"].schema if str(k) in ("connection", "delivery_defaults", "advanced")] == [
        "connection",
        "delivery_defaults",
        "advanced",
    ]
    assert not connection.options["collapsed"]
    suggested = _section_suggested(connection)
    assert suggested["host"] == "smtp.example.com"
    # the password is never shown
    assert "password" not in suggested

    result = await _configure(
        hass,
        result,
        {
            "enabled": True,
            "advanced": {"load": True},
            "connection": {"host": "smtp.example.com", "port": 465.0, "encryption": "tls"},
        },
    )
    assert result["reason"] == "reconfigure_successful"
    # left empty, the password is kept, and the port is a whole number
    assert dict(subentry.data)["connection"] == {
        "host": "smtp.example.com",
        "port": 465,
        "encryption": "tls",
        "password": "secret",
    }

    # a connection with no host isn't valid
    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=subentry.subentry_id)
    result = await _configure(
        hass, result, {"enabled": True, "advanced": {"load": True}, "connection": {"host": "", "port": 25.0}}
    )
    assert result["errors"] == {"base": "invalid_transport"}


async def test_invalid_transport(hass: HomeAssistant) -> None:
    entry = await _entry(hass, subentries_data=[_generic_subentry()])
    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=_transports(entry)["generic"].subentry_id)

    result = await _configure(
        hass,
        result,
        {"enabled": True, "advanced": {"load": True}, "delivery_defaults": {"other_delivery_defaults": {"colour": "red"}}},
    )
    assert result["errors"] == {"base": "invalid_transport"}
    assert "colour" in result["description_placeholders"]["error"]

    result = await _configure(
        hass, result, {"enabled": True, "advanced": {"load": True}, "delivery_defaults": {"action": "not an action"}}
    )
    assert result["errors"] == {"base": "invalid_transport"}

    result = await _configure(
        hass,
        result,
        {"enabled": True, "advanced": {"load": True}, "delivery_defaults": {"custom_target": ["email:not-an-address"]}},
    )
    assert result["errors"] == {"base": "invalid_custom_target"}


async def test_yaml_transports_imported_once_with_repair(hass: HomeAssistant) -> None:
    yaml_config = {
        "delivery": DELIVERY,
        "transports": {
            "generic": {
                "delivery_defaults": {
                    "conditions": [
                        {"condition": "template", "value_template": "{{ true }}"},
                        {"condition": "time", "after": "22:00:00"},
                    ]
                }
            }
        },
    }
    entry = await _entry(hass, yaml_config)

    data = dict(_transports(entry)["generic"].data)
    # stored as written, not as validated, so it can be stored and validated again
    json.dumps(data)
    assert data["delivery_defaults"]["conditions"] == [
        {"condition": "template", "value_template": "{{ true }}"},
        {"condition": "time", "after": "22:00:00"},
    ]
    assert ir.async_get(hass).async_get_issue(DOMAIN, YAML_TRANSPORTS_ISSUE_ID) is not None


async def test_no_yaml_transports_no_repair(hass: HomeAssistant) -> None:
    await _entry(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, YAML_TRANSPORTS_ISSUE_ID) is None


def test_raw_config_round_trips(hass: HomeAssistant) -> None:
    raw = {
        "delivery_defaults": {
            "conditions": [{"condition": "time", "after": "22:00:00"}],
            "options": {"delay": "0:05:00", "names": ["a", "b"]},
        }
    }
    validated = TRANSPORT_SCHEMA(raw)
    assert as_raw_config(TRANSPORT_SCHEMA(as_raw_config(validated))) == as_raw_config(validated)
    assert as_raw_config({"t": Template("{{ 1 }}", hass), "at": dt.time(7, 30), "for": dt.timedelta(minutes=5), "s": {1}}) == {
        "t": "{{ 1 }}",
        "at": "07:30:00",
        "for": "0:05:00",
        "s": [1],
    }


DEPRECATED = {
    "device_domain": ["alexa_devices"],
    "device_discovery": True,
    "device_model_include": ["Echo.*"],
    "delivery_defaults": {"selection": ["explicit"], "options": {"chime_aliases": {}}},
}


async def test_deprecated_settings_raise_repair_cleared_by_saving(hass: HomeAssistant) -> None:
    subentry_data = ConfigSubentryData(
        data=DEPRECATED, subentry_type=SUBENTRY_TYPE_TRANSPORT, title="generic", unique_id="generic"
    )
    entry = await _entry(hass, subentries_data=[subentry_data])
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "transport_generic_deprecated_config")
    assert issue is not None
    assert issue.translation_placeholders == {
        "transport": "generic",
        "keys": "device_domain, device_discovery, device_model_include, delivery_defaults.selection",
    }

    subentry = _transports(entry)["generic"]
    result = await _start(hass, entry, SOURCE_RECONFIGURE, subentry_id=subentry.subentry_id)
    # shown as their replacements
    suggested = _section_suggested(_section(result, "delivery_defaults"))
    assert suggested["inclusion"] == ["explicit"]
    assert suggested["options"]["device_domain"] == ["alexa_devices"]
    result = await _configure(
        hass,
        result,
        {
            "enabled": True,
            "advanced": {"load": True},
            "delivery_defaults": {"inclusion": suggested["inclusion"], "options": suggested["options"]},
        },
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()

    assert dict(subentry.data) == {
        "enabled": True,
        "load": True,
        "delivery_defaults": {
            "inclusion": ["explicit"],
            "options": {
                "chime_aliases": {},
                "device_domain": ["alexa_devices"],
                "device_discovery": True,
                "device_model_select": {"include": ["Echo.*"], "exclude": None},
            },
        },
    }
    # saved, and so reloaded, without them, so the repair is cleared
    assert ir.async_get(hass).async_get_issue(DOMAIN, "transport_generic_deprecated_config") is None


async def test_deprecated_repair_cleared_for_removed_transport(hass: HomeAssistant) -> None:
    subentry_data = ConfigSubentryData(data=DEPRECATED, subentry_type=SUBENTRY_TYPE_TRANSPORT, title="chime", unique_id="chime")
    entry = await _entry(hass, subentries_data=[subentry_data])
    assert ir.async_get(hass).async_get_issue(DOMAIN, "transport_chime_deprecated_config") is not None
    hass.config_entries.async_remove_subentry(entry, _transports(entry)["chime"].subentry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "transport_chime_deprecated_config") is None


async def test_running_engine_leaves_subentry_data_alone(hass: HomeAssistant) -> None:
    """The engine adds defaults to the configuration it's given, which mustn't reach what's stored"""
    data = {"delivery_defaults": {"action": "notify.send_message", "options": {"strip_urls": True}}}
    entry = await _entry(
        hass,
        subentries_data=[
            ConfigSubentryData(data=data, subentry_type=SUBENTRY_TYPE_TRANSPORT, title="generic", unique_id="generic")
        ],
    )
    assert entry.runtime_data.context.delivery_registry.transports["generic"].delivery_defaults.options["raw"] is False
    assert dict(_transports(entry)["generic"].data) == data
