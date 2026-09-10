from __future__ import annotations

from homeassistant.const import CONF_HOST

from custom_components.supernotify.const import (
    ATTR_EMAIL,
    ATTR_SCENARIOS_CONSTRAIN,
    CONF_CONNECTION,
    CONF_DATA,
    CONF_DELIVERY_DEFAULTS,
    CONF_OPTIONS,
    OPTION_SENDER,
)
from custom_components.supernotify.schema import NOTIFY_ACTION_SCHEMA, TARGET_SCHEMA, TRANSPORT_SCHEMA


def test_transport_schema_sender_stays_a_string() -> None:
    """Regression test: vol.Email (uncalled) previously returned a validator function.

    instead of the validated address, so downstream code (e.g. email.utils.formataddr)
    blew up trying to call str methods on a function object.
    """
    validated = TRANSPORT_SCHEMA({
        CONF_CONNECTION: {CONF_HOST: "smtp.example.com"},
        CONF_DELIVERY_DEFAULTS: {CONF_OPTIONS: {OPTION_SENDER: "hass@example.com"}},
    })
    assert isinstance(validated[CONF_DELIVERY_DEFAULTS][CONF_OPTIONS][OPTION_SENDER], str)
    assert validated[CONF_DELIVERY_DEFAULTS][CONF_OPTIONS][OPTION_SENDER] == "hass@example.com"


def test_target_schema_email_list_stays_strings() -> None:
    validated = TARGET_SCHEMA({ATTR_EMAIL: ["tester1@example.com"]})
    assert validated[ATTR_EMAIL] == ["tester1@example.com"]
    assert all(isinstance(address, str) for address in validated[ATTR_EMAIL])


def test_notify_action_schema_allows_null_in_nested_data() -> None:
    """Regression test: the HA UI leaves an untouched multi-select field (e.g.

    constrain_scenarios) as an explicit null rather than omitting it, and that null can end
    up nested inside the generic passthrough `data:` field alongside other extra data. That
    nested value previously failed schema validation, since DATA_SCHEMA only accepted str,
    int, bool, float, dict or list - not None.
    """
    validated = NOTIFY_ACTION_SCHEMA({
        "message": "Frigate Daily Summary",
        "target": ["person.home_owner"],
        CONF_DATA: {"delivery": ["plain_email"], ATTR_SCENARIOS_CONSTRAIN: None},
    })
    assert validated[CONF_DATA][ATTR_SCENARIOS_CONSTRAIN] is None
