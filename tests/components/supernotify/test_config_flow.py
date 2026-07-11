"""Tests for the SuperNotify config flow (Phase 1).

Covers:
  * async_step_user — form display, entry creation with correct nested mapping,
    single-instance abort.
  * async_step_import — YAML import, marker handling, global/items split.
  * pure helpers — _split_global_vs_items, _form_to_entry_data.

Pattern: pytest-homeassistant-custom-component (already a dev dependency).
File path in the package: tests/components/supernotify/test_config_flow.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ENABLED
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from custom_components.supernotify import ATTR_IMPORTED_FROM_YAML, DOMAIN
from custom_components.supernotify.config_flow import (
    _form_to_entry_data,
    _split_global_vs_items,
)
from custom_components.supernotify.const import (
    ATTR_DUPE_POLICY_MT,
    ATTR_DUPE_POLICY_MTSLP,
    CONF_ARCHIVE,
    CONF_ARCHIVE_DAYS,
    CONF_DUPE_CHECK,
    CONF_DUPE_POLICY,
    CONF_HOUSEKEEPING,
    CONF_MEDIA_PATH,
    CONF_MEDIA_STORAGE_DAYS,
    CONF_MEDIA_URL_PREFIX,
    CONF_MOBILE_DISCOVERY,
    CONF_RECIPIENTS_DISCOVERY,
    CONF_SIZE,
    CONF_SNOOZE,
    CONF_SNOOZE_TIME,
    CONF_TEMPLATE_PATH,
    CONF_TTL,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


_VALID_USER_INPUT = {
    CONF_TEMPLATE_PATH: "/config/templates/supernotify",
    CONF_MEDIA_PATH: "supernotify/media",
    CONF_MEDIA_URL_PREFIX: "/supernotify/media",
    CONF_MOBILE_DISCOVERY: True,
    CONF_RECIPIENTS_DISCOVERY: False,
    "archive_enabled": True,
    "archive_days": 5,
    "dupe_ttl": 90,
    "dupe_size": 50,
    "dupe_policy": ATTR_DUPE_POLICY_MT,
    "snooze_seconds": 1800,
    "media_storage_days": 10,
}


# --------------------------------------------------------------------------- #
# async_step_user
# --------------------------------------------------------------------------- #
async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """The user step shows a form when called without input."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_creates_entry_with_nested_mapping(hass: HomeAssistant) -> None:
    """Valid input creates an entry; flat form fields map to nested structure."""
    init = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(init["flow_id"], _VALID_USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    assert data[CONF_TEMPLATE_PATH] == "/config/templates/supernotify"
    assert data[CONF_MOBILE_DISCOVERY] is True
    assert data[CONF_RECIPIENTS_DISCOVERY] is False
    # Nested groups rebuilt from flat fields:
    assert data[CONF_ARCHIVE] == {CONF_ENABLED: True, CONF_ARCHIVE_DAYS: 5}
    assert data[CONF_DUPE_CHECK] == {
        CONF_TTL: 90,
        CONF_SIZE: 50,
        CONF_DUPE_POLICY: ATTR_DUPE_POLICY_MT,
    }
    assert data[CONF_SNOOZE] == {CONF_SNOOZE_TIME: 1800}
    assert data[CONF_HOUSEKEEPING] == {CONF_MEDIA_STORAGE_DAYS: 10}


async def test_user_step_single_instance(hass: HomeAssistant) -> None:
    """A second setup is aborted — only one SuperNotify instance is supported."""
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    # single_config_entry: true in the manifest makes HA core abort with
    # "single_instance_allowed" BEFORE the flow's unique_id guard
    # (which would abort with "already_configured") is reached.
    assert result["reason"] == "single_instance_allowed"


# --------------------------------------------------------------------------- #
# async_step_import
# --------------------------------------------------------------------------- #
async def test_import_splits_global_and_items_and_keeps_marker(
    hass: HomeAssistant,
) -> None:
    """YAML import: globals into data, item collections into options, marker kept."""
    import_data = {
        CONF_TEMPLATE_PATH: "/config/templates/supernotify",
        CONF_MOBILE_DISCOVERY: True,
        "delivery": {"alexa_announce": {"transport": "alexa"}},
        "scenarios": {"morning": {}},
        ATTR_IMPORTED_FROM_YAML: True,
    }
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    data = result["data"]
    options = result["options"]
    # Marker preserved so async_setup_entry won't double-load the service.
    assert data[ATTR_IMPORTED_FROM_YAML] is True
    # Globals in data, items NOT in data.
    assert data[CONF_TEMPLATE_PATH] == "/config/templates/supernotify"
    assert "delivery" not in data
    # Item collections preserved verbatim in options.
    assert options["delivery"] == {"alexa_announce": {"transport": "alexa"}}
    assert options["scenarios"] == {"morning": {}}


async def test_import_without_marker_defaults_false(hass: HomeAssistant) -> None:
    """Import with no marker stores imported_from_yaml=False."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_TEMPLATE_PATH: "/config/templates/supernotify"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_IMPORTED_FROM_YAML] is False


async def test_import_single_instance(hass: HomeAssistant) -> None:
    """A second import is aborted (single instance)."""
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={ATTR_IMPORTED_FROM_YAML: True},
    )
    assert result["type"] is FlowResultType.ABORT
    # See test_user_step_single_instance: HA core aborts single_config_entry
    # integrations with "single_instance_allowed" (import flows included).
    assert result["reason"] == "single_instance_allowed"


# --------------------------------------------------------------------------- #
# form schema structure
# --------------------------------------------------------------------------- #
def _schema_fields(result) -> set[str]:
    """Field names exposed by a form's data_schema."""
    return {marker.schema for marker in result["data_schema"].schema}


def _schema_defaults(result) -> dict:
    """Default values pre-filled in a form's data_schema."""
    return {marker.schema: marker.default() for marker in result["data_schema"].schema if marker.default is not vol.UNDEFINED}


_EXPECTED_FIELDS = {
    CONF_TEMPLATE_PATH,
    CONF_MEDIA_PATH,
    CONF_MEDIA_URL_PREFIX,
    CONF_MOBILE_DISCOVERY,
    CONF_RECIPIENTS_DISCOVERY,
    "archive_enabled",
    "archive_days",
    "dupe_ttl",
    "dupe_size",
    "dupe_policy",
    "snooze_seconds",
    "media_storage_days",
}


async def test_user_form_exposes_all_global_fields(hass: HomeAssistant) -> None:
    """The user form schema contains every global-settings field."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert _schema_fields(result) >= _EXPECTED_FIELDS


async def test_reconfigure_form_prefilled_from_entry(hass: HomeAssistant) -> None:
    """Pre-fill the reconfigure form with the entry's current values.

    Not the schema defaults.
    """
    from custom_components.supernotify.config_flow import _form_to_entry_data

    initial = _form_to_entry_data(_VALID_USER_INPUT)  # archive_days == 5
    initial[ATTR_IMPORTED_FROM_YAML] = True
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=initial)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    defaults = _schema_defaults(result)
    # Current entry value (5), not the schema default (3):
    assert defaults["archive_days"] == 5
    assert defaults[CONF_TEMPLATE_PATH] == "/config/templates/supernotify"
    assert defaults[CONF_MOBILE_DISCOVERY] is True


# --------------------------------------------------------------------------- #
# async_step_reconfigure
# --------------------------------------------------------------------------- #
async def test_reconfigure_updates_entry_in_place(hass: HomeAssistant) -> None:
    """Reconfigure updates the existing entry in place.

    It does not create a new one, and preserves the imported-from-YAML marker.
    """
    from custom_components.supernotify.config_flow import _form_to_entry_data
    from custom_components.supernotify.const import CONF_ARCHIVE_DAYS

    initial = _form_to_entry_data(_VALID_USER_INPUT)
    initial[ATTR_IMPORTED_FROM_YAML] = True
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=initial)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    new_input = dict(_VALID_USER_INPUT)
    new_input["archive_days"] = 9
    result = await hass.config_entries.flow.async_configure(result["flow_id"], new_input)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # No second entry created.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    # Data updated in place.
    assert entry.data[CONF_ARCHIVE] == {CONF_ENABLED: True, CONF_ARCHIVE_DAYS: 9}
    # Marker preserved through the update.
    assert entry.data[ATTR_IMPORTED_FROM_YAML] is True


# --------------------------------------------------------------------------- #
# pure helpers (no hass required)
# --------------------------------------------------------------------------- #
def test_split_global_vs_items() -> None:
    """Item keys go to options, everything else stays global."""
    config = {
        CONF_TEMPLATE_PATH: "/x",
        CONF_MOBILE_DISCOVERY: True,
        "delivery": {"d": {}},
        "scenarios": {"s": {}},
        "recipients": [{"person": "person.a"}],
        "cameras": [],
        "links": [],
        "action_groups": {},
        "transports": {},
    }
    global_data, items = _split_global_vs_items(config)

    assert global_data == {CONF_TEMPLATE_PATH: "/x", CONF_MOBILE_DISCOVERY: True}
    assert set(items) == {
        "delivery",
        "scenarios",
        "recipients",
        "cameras",
        "links",
        "action_groups",
        "transports",
    }
    assert items["delivery"] == {"d": {}}


def test_form_to_entry_data_builds_nested_groups() -> None:
    """Flat form fields are rebuilt into the nested config the runtime expects."""
    data = _form_to_entry_data(_VALID_USER_INPUT)

    assert data[CONF_ARCHIVE] == {CONF_ENABLED: True, CONF_ARCHIVE_DAYS: 5}
    assert data[CONF_DUPE_CHECK] == {
        CONF_TTL: 90,
        CONF_SIZE: 50,
        CONF_DUPE_POLICY: ATTR_DUPE_POLICY_MT,
    }
    assert data[CONF_SNOOZE] == {CONF_SNOOZE_TIME: 1800}
    assert data[CONF_HOUSEKEEPING] == {CONF_MEDIA_STORAGE_DAYS: 10}
    # No stray flat keys leaked into the nested structure.
    assert "archive_enabled" not in data
    assert "dupe_ttl" not in data
    # Default dupe policy constant is a valid choice (sanity).
    assert ATTR_DUPE_POLICY_MTSLP  # imported/used marker


def test_entry_data_to_form_round_trips() -> None:
    """_entry_data_to_form is the inverse of _form_to_entry_data."""
    from custom_components.supernotify.config_flow import _entry_data_to_form

    nested = _form_to_entry_data(_VALID_USER_INPUT)
    flat = _entry_data_to_form(nested)
    assert flat == _VALID_USER_INPUT


def test_entry_data_to_form_uses_defaults_when_empty() -> None:
    """With empty data, the flat form falls back to schema defaults."""
    from custom_components.supernotify.config_flow import _entry_data_to_form

    flat = _entry_data_to_form({})
    assert flat["archive_enabled"] is False
    assert flat["archive_days"] == 3
    assert flat["dupe_ttl"] == 120
    assert flat["snooze_seconds"] == 3600
    assert flat["media_storage_days"] == 7


# --------------------------------------------------------------------------- #
# _jsonify — regression for "Type is not JSON serializable" on entry storage
# --------------------------------------------------------------------------- #
# SUPERNOTIFY_SCHEMA validates the imported YAML and coerces some delivery fields
# into non-JSON-serializable objects (Template, the MessageOnlyPolicy enum, a
# ConditionsChecker instance). Storing those in the config entry raised
# "Type is not JSON serializable: Template" the moment a subentry was added or the
# entry was reconfigured. _jsonify converts every non-primitive to a string so the
# entry can be persisted. These tests guard that fix.
def test_jsonify_makes_validated_config_serializable() -> None:
    """_jsonify converts Template/enum/objects to strings, recursively.

    Primitives, dicts and lists stay intact; the result must be JSON-serializable.
    """
    import json
    from enum import Enum

    from custom_components.supernotify.config_flow import _jsonify

    class _Policy(Enum):
        STANDARD = "STANDARD"

    class _ConditionsChecker:  # stand-in for the runtime object
        pass

    class _FakeTemplate:  # mimics homeassistant Template: has a .template str
        def __init__(self, template: str) -> None:
            self.template = template

    raw = {
        "delivery": {
            "alexa": {
                "volume": _FakeTemplate("{{ 0.2 }}"),
                "message_usage": _Policy.STANDARD,
                "conditions": _ConditionsChecker(),
                "enabled": True,
                "priority": ["high", "low"],
                "nested": {"msg": _FakeTemplate("{{ notification_message }}")},
            }
        },
        "count": 5,
        "flag": False,
        "empty": None,
    }
    out = _jsonify(raw)

    # The whole structure is now storable.
    json.dumps(out)  # must not raise

    alexa = out["delivery"]["alexa"]
    assert alexa["volume"] == "{{ 0.2 }}"  # Template -> source string
    assert isinstance(alexa["message_usage"], str)  # enum -> str
    assert isinstance(alexa["conditions"], str)  # object -> str
    assert alexa["enabled"] is True  # primitive preserved
    assert alexa["priority"] == ["high", "low"]  # list preserved
    assert alexa["nested"]["msg"] == "{{ notification_message }}"  # recursion
    assert out["count"] == 5
    assert out["flag"] is False
    assert out["empty"] is None


def test_jsonify_with_real_homeassistant_template() -> None:
    """A real HA Template is reduced to its source string (not str(obj))."""
    from homeassistant.helpers.template import Template

    from custom_components.supernotify.config_flow import _jsonify

    out = _jsonify({"volume": Template("{{ 0.3 }}")})
    assert out["volume"] == "{{ 0.3 }}"


async def test_import_jsonifies_non_serializable_delivery(hass: HomeAssistant) -> None:
    """Import of YAML with a Template yields JSON-serializable entry options.

    Regression for the 'Type is not JSON serializable: Template' crash on the
    first entry update after import.
    """
    import json

    from homeassistant.helpers.template import Template

    import_data = {
        CONF_TEMPLATE_PATH: "/config/templates/supernotify",
        "delivery": {"alexa": {"volume": Template("{{ 0.2 }}")}},
        ATTR_IMPORTED_FROM_YAML: True,
    }
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Both stores must be JSON-serializable, or the first entry update
    # (subentry add, reconfigure) crashes the save of the whole entry.
    json.dumps(result["data"])  # must not raise
    json.dumps(result["options"])  # must not raise
    # The Template survives as its source string, not as an object.
    assert result["options"]["delivery"]["alexa"]["volume"] == "{{ 0.2 }}"
