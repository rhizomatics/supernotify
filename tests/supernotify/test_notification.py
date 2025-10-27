import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.const import CONF_ACTION, CONF_EMAIL, CONF_METHOD, CONF_TARGET
from pytest_unordered import unordered

from custom_components.supernotify import (
    ATTR_DATA,
    ATTR_MEDIA,
    ATTR_MEDIA_CAMERA_DELAY,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_SCENARIOS_APPLY,
    CONF_DELIVERY,
    CONF_DELIVERY_SELECTION,
    CONF_MEDIA,
    CONF_RECIPIENTS,
    DELIVERY_SELECTION_EXPLICIT,
    DELIVERY_SELECTION_IMPLICIT,
    METHOD_EMAIL,
    METHOD_GENERIC,
    MessageOnlyPolicy,
)
from custom_components.supernotify.configuration import Context
from custom_components.supernotify.delivery_method import DeliveryMethod
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.methods.email import EmailDeliveryMethod
from custom_components.supernotify.methods.generic import GenericDeliveryMethod
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.scenario import Scenario


async def test_simple_create(mock_context: Context) -> None:
    mock_context.deliveries = {"plain_email": {}, "mobile": {"title": "mobile notification"}, "chime": {}}
    mock_context.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"]}
    uut = Notification(mock_context, "testing 123")
    await uut.initialize()
    assert uut.enabled_scenarios == {}
    assert uut.applied_scenario_names == []
    assert uut.target == []
    assert uut.message("plain_email") == "testing 123"
    assert uut.title("mobile") == "mobile notification"
    assert uut.priority == "medium"
    assert uut.delivery_overrides == {}
    assert uut.delivery_selection == DELIVERY_SELECTION_IMPLICIT
    assert uut.recipients_override is None
    assert uut.selected_delivery_names == unordered(["plain_email", "mobile"])


async def test_explicit_delivery(mock_context: Context) -> None:
    mock_context.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"]}
    mock_context.deliveries = {"plain_email": {}, "mobile": {}, "chime": {}}
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={CONF_DELIVERY_SELECTION: DELIVERY_SELECTION_EXPLICIT, CONF_DELIVERY: "mobile"},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert uut.selected_delivery_names == ["mobile"]


async def test_scenario_delivery(mock_context: Context, mock_scenario: Scenario) -> None:
    mock_context.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "mockery": ["chime"]}
    mock_context.deliveries = {"plain_email": {}, "mobile": {}, "chime": {}}
    mock_context.scenarios = {"mockery": mock_scenario}
    uut = Notification(mock_context, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime")


async def test_explicit_list_of_deliveries(mock_context: Context) -> None:
    mock_context.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}
    mock_context.deliveries = {"plain_email": {}, "mobile": {}, "chime": {}}
    uut = Notification(mock_context, "testing 123", action_data={CONF_DELIVERY: "mobile"})
    await uut.initialize()
    assert uut.selected_delivery_names == ["mobile"]


async def test_generate_recipients_from_entities(mock_context: Context) -> None:
    delivery = {
        "chatty": {
            CONF_METHOD: METHOD_GENERIC,
            CONF_ACTION: "custom.tweak",
            CONF_TARGET: ["custom.light_1", "custom.switch_2"],
        }
    }
    mock_context.deliveries = delivery
    uut = Notification(mock_context, "testing 123")
    generic = GenericDeliveryMethod(mock_context.hass, mock_context, delivery)
    await generic.initialize()
    recipients = uut.generate_recipients("chatty", generic)
    assert recipients == [{"target": "custom.light_1"}, {"target": "custom.switch_2"}]


async def test_generate_recipients_from_recipients(mock_context: Context) -> None:
    delivery = {
        "chatty": {
            CONF_METHOD: METHOD_GENERIC,
            CONF_ACTION: "custom.tweak",
            CONF_RECIPIENTS: [{"target": "custom.light_1"}, {"person": "joey.soapy"}],
        }
    }
    mock_context.deliveries = delivery
    uut = Notification(mock_context, "testing 123")
    generic = GenericDeliveryMethod(mock_context.hass, mock_context, delivery)
    await generic.initialize()
    recipients: list[dict[str, Any]] = uut.generate_recipients("chatty", generic)
    assert recipients == [{"target": "custom.light_1"}, {"person": "joey.soapy"}]


async def test_explicit_recipients_only_restricts_people_targets(mock_context: Context) -> None:
    delivery = {
        "chatty": {CONF_METHOD: METHOD_GENERIC, CONF_ACTION: "notify.slackity", CONF_TARGET: ["chan1", "chan2"]},
        "mail": {CONF_METHOD: METHOD_EMAIL, CONF_ACTION: "notify.smtp"},
    }
    mock_context.people = {"person.bob": {CONF_EMAIL: "bob@test.com"}, "person.jane": {CONF_EMAIL: "jane@test.com"}}
    mock_context.deliveries = delivery
    uut = Notification(mock_context, "testing 123")
    generic = GenericDeliveryMethod(mock_context.hass, mock_context, delivery)
    await generic.initialize()
    recipients = uut.generate_recipients("chatty", generic)
    assert recipients == [{"target": "chan1"}, {"target": "chan2"}]
    bundles = uut.generate_envelopes("chatty", generic, recipients)
    assert bundles == [Envelope("chatty", uut, targets=["chan1", "chan2"])]
    email = EmailDeliveryMethod(mock_context.hass, mock_context, delivery)  # type: ignore
    await email.initialize()
    recipients = uut.generate_recipients("mail", email)
    assert recipients == [{"email": "bob@test.com"}, {"email": "jane@test.com"}]
    bundles = uut.generate_envelopes("mail", email, recipients)
    assert bundles == [Envelope("mail", uut, targets=["bob@test.com", "jane@test.com"])]


async def test_filter_recipients(mock_context: Context) -> None:
    uut = Notification(mock_context, "testing 123")
    await uut.initialize()

    assert len(uut.filter_people_by_occupancy("all_in")) == 0
    assert len(uut.filter_people_by_occupancy("all_out")) == 0
    assert len(uut.filter_people_by_occupancy("any_in")) == 2
    assert len(uut.filter_people_by_occupancy("any_out")) == 2
    assert len(uut.filter_people_by_occupancy("only_in")) == 1
    assert len(uut.filter_people_by_occupancy("only_out")) == 1

    assert {r["person"] for r in uut.filter_people_by_occupancy("only_out")} == {"person.new_home_owner"}
    assert {r["person"] for r in uut.filter_people_by_occupancy("only_in")} == {"person.bidey_in"}


async def test_build_targets_for_simple_case(mock_context: Context) -> None:
    method = GenericDeliveryMethod(mock_context.hass, mock_context, {})
    await method.initialize()
    # mock_context.deliveries={'testy':method}
    uut = Notification(mock_context, "testing 123")
    recipients = uut.generate_recipients("", method)
    bundles = uut.generate_envelopes("", method, recipients)
    assert bundles == [Envelope("", uut)]


async def test_dict_of_delivery_tuning_does_not_restrict_deliveries(mock_context: Context) -> None:
    mock_context.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}
    mock_context.deliveries = {"plain_email": {}, "mobile": {}, "chime": {}}
    uut = Notification(mock_context, "testing 123", action_data={CONF_DELIVERY: {"mobile": {}}})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile")


async def test_snapshot_url(mock_context: Context) -> None:
    uut = Notification(mock_context, "testing 123", action_data={CONF_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/my_local_image"}})
    await uut.initialize()
    original_image_path: Path = Path(tempfile.gettempdir()) / "image_a.jpg"
    with patch(
        "custom_components.supernotify.notification.snapshot_from_url", return_value=original_image_path
    ) as mock_snapshot:
        retrieved_image_path = await uut.grab_image("example")
        assert retrieved_image_path == original_image_path
        assert mock_snapshot.called
        mock_snapshot.reset_mock()
        retrieved_image_path = await uut.grab_image("example")
        assert retrieved_image_path == original_image_path
        # notification caches image for multiple deliveries
        mock_snapshot.assert_not_called()


async def test_camera_entity(mock_context: Context) -> None:
    uut = Notification(mock_context, "testing 123", action_data={CONF_MEDIA: {ATTR_MEDIA_CAMERA_ENTITY_ID: "camera.lobby"}})
    await uut.initialize()
    original_image_path: Path = Path(tempfile.gettempdir()) / "image_b.jpg"
    with patch("custom_components.supernotify.notification.snap_camera", return_value=original_image_path) as mock_snap_cam:
        retrieved_image_path = await uut.grab_image("example")
        assert retrieved_image_path == original_image_path
        assert mock_snap_cam.called
        mock_snap_cam.reset_mock()
        retrieved_image_path = await uut.grab_image("example")
        assert retrieved_image_path == original_image_path
        # notification caches image for multiple deliveries
        mock_snap_cam.assert_not_called()


async def test_message_usage(mock_context: Context, mock_method: DeliveryMethod) -> None:
    mock_context.deliveries = {"push": {CONF_METHOD: "unit_testing"}}
    mock_context.delivery_by_scenario = {"DEFAULT": ["push"]}
    mock_context.delivery_method.return_value = mock_method  # type: ignore[attr-defined]

    uut = Notification(
        mock_context,
        "testing 123",
        title="the big title"
    )
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") == "the big title"

    mock_method.option_str.return_value = MessageOnlyPolicy.USE_TITLE  # type: ignore
    uut = Notification(
        mock_context,
        "testing 123",
        title="the big title"
    )
    await uut.initialize()
    assert uut.message("push") == "the big title"
    assert uut.title("push") is None

    mock_method.option_str.return_value = MessageOnlyPolicy.USE_TITLE  # type: ignore
    uut = Notification(
        mock_context,
        "testing 123"
    )
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") is None

    mock_method.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE  # type: ignore
    uut = Notification(
        mock_context,
        "testing 123",
        title="the big title"
    )
    await uut.initialize()
    assert uut.message("push") == "the big title testing 123"
    assert uut.title("push") is None

    mock_method.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE  # type: ignore
    uut = Notification(
        mock_context,
        "testing 123"
    )
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") is None


async def test_merge(mock_context: Context) -> None:
    mock_context.scenarios = {
        "Alarm": Scenario("Alarm", {"media": {"jpeg_opts": {"quality": 30}, "snapshot_url": "/bar/789"}}, mock_context.hass)  # type: ignore
    }
    mock_context.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}
    mock_context.deliveries = {"plain_email": {}, "mobile": {}, "chime": {}}
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={
            ATTR_SCENARIOS_APPLY: "Alarm",
            ATTR_MEDIA: {ATTR_MEDIA_CAMERA_DELAY: 11, ATTR_MEDIA_SNAPSHOT_URL: "/foo/123"},
        },
    )
    await uut.initialize()
    assert uut.merge(ATTR_MEDIA, "plain_email") == {
        "jpeg_opts": {"quality": 30},
        "camera_delay": 11,
        "snapshot_url": "/foo/123",
    }
    assert uut.merge(ATTR_DATA, "plain_email") == {}
