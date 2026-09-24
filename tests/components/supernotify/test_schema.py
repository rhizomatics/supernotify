from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.supernotify.const import (
    ATTR_EMAIL,
    ATTR_MEDIA,
    ATTR_MEDIA_SNAPSHOT_PATH,
    ATTR_SCENARIOS_CONSTRAIN,
    CONF_DATA,
    CONF_DELIVERY_DEFAULTS,
    CONF_OCCUPANCY,
    CONF_PERSON,
    CONF_TEMPLATE,
    CONF_USER_ID,
    OCCUPANCY_ALL_IN,
)
from custom_components.supernotify.schema import NOTIFY_ACTION_SCHEMA, RECIPIENT_SCHEMA, TARGET_SCHEMA, TRANSPORT_SCHEMA


def test_transport_delivery_defaults_accepts_delivery_only_fields() -> None:
    """delivery_defaults can now set template/message/title/alias/occupancy/conditions -
    fields previously only valid on an explicit Delivery - so a Transport alone can carry
    them without needing a Delivery to be defined."""
    validated = TRANSPORT_SCHEMA({
        CONF_DELIVERY_DEFAULTS: {CONF_TEMPLATE: "transport_template", CONF_OCCUPANCY: OCCUPANCY_ALL_IN},
    })
    assert validated[CONF_DELIVERY_DEFAULTS][CONF_TEMPLATE] == "transport_template"
    assert validated[CONF_DELIVERY_DEFAULTS][CONF_OCCUPANCY] == OCCUPANCY_ALL_IN


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


def test_notify_action_schema_accepts_media_snapshot_image_path() -> None:
    """Regression test: snapshot_image_path is documented and handled by media_grab, but was
    missing from MEDIA_SCHEMA so validation rejected it as an extra key."""
    validated = NOTIFY_ACTION_SCHEMA({
        "message": "hello",
        ATTR_MEDIA: {ATTR_MEDIA_SNAPSHOT_PATH: "/config/media/supernotify/image/shot.jpg"},
    })
    assert validated[ATTR_MEDIA][ATTR_MEDIA_SNAPSHOT_PATH] == "/config/media/supernotify/image/shot.jpg"


def test_recipient_schema_accepts_user_id_without_person() -> None:
    """A household that only sets up HA Users (no Person records) can still be a recipient."""
    validated = RECIPIENT_SCHEMA({CONF_USER_ID: "abc123"})
    assert validated[CONF_USER_ID] == "abc123"
    assert CONF_PERSON not in validated


def test_recipient_schema_accepts_person_without_user_id() -> None:
    validated = RECIPIENT_SCHEMA({CONF_PERSON: "person.alice"})
    assert validated[CONF_PERSON] == "person.alice"


def test_recipient_schema_rejects_recipient_with_neither_person_nor_user_id() -> None:
    with pytest.raises(vol.Invalid):
        RECIPIENT_SCHEMA({"alias": "Nobody"})
