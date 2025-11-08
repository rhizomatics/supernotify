import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from homeassistant.const import CONF_ACTION, CONF_EMAIL, CONF_TARGET
from homeassistant.core import HomeAssistant
from pytest_unordered import unordered

from custom_components.supernotify import (
    ATTR_DATA,
    ATTR_MEDIA,
    ATTR_MEDIA_CAMERA_DELAY,
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_SCENARIOS_APPLY,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_MEDIA,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_TRANSPORT,
    DELIVERY_SELECTION_EXPLICIT,
    DELIVERY_SELECTION_IMPLICIT,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.media_grab import grab_image
from custom_components.supernotify.model import MessageOnlyPolicy, Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.scenario import Scenario
from custom_components.supernotify.transport import OPTION_TARGET_CATEGORIES, Transport
from custom_components.supernotify.transports.email import EmailTransport
from custom_components.supernotify.transports.generic import GenericTransport
from custom_components.supernotify.transports.mobile_push import MobilePushTransport

from .doubles_lib import build_delivery_from_config


async def test_simple_create(mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    mock_context.deliveries["mobile"] = Delivery(
        "mobile", {"title": "mobile notification"}, MobilePushTransport(mock_hass, mock_context, mock_people_registry)
    )
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"]}
    uut = Notification(mock_context, mock_people_registry, "testing 123")
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


async def test_explicit_delivery(mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile", "chime"]}

    # string forces explicit selection
    uut = Notification(
        mock_context,
        mock_people_registry,
        "testing 123",
        action_data={CONF_DELIVERY: "mobile"},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert uut.selected_delivery_names == ["mobile"]

    # list forces explicit selection
    uut = Notification(
        mock_context,
        mock_people_registry,
        "testing 123",
        action_data={CONF_DELIVERY: ["mobile", "chime"]},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert uut.selected_delivery_names == unordered(["mobile", "chime"])

    # dict doesn't force explicit selection
    uut = Notification(
        mock_context,
        mock_people_registry,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile": {CONF_DATA: {"foo": "bar"}}}},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_IMPLICIT
    assert uut.selected_delivery_names == unordered(["mobile", "plain_email", "chime"])


async def test_scenario_delivery(
    mock_hass: HomeAssistant, mock_context: Context, mock_scenario: Scenario, mock_people_registry: PeopleRegistry
) -> None:
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "mockery": ["chime"]}

    mock_context.scenario_registry.scenarios = {"mockery": mock_scenario}
    uut = Notification(mock_context, mock_people_registry, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime")


async def test_explicit_list_of_deliveries(
    mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry
) -> None:
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}

    uut = Notification(mock_context, mock_people_registry, "testing 123", action_data={CONF_DELIVERY: "mobile"})
    await uut.initialize()
    assert uut.selected_delivery_names == ["mobile"]


async def test_generate_recipients_from_entities(
    mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry
) -> None:
    delivery = {
        "chatty": {CONF_ACTION: "custom.tweak", CONF_TARGET: ["custom.light_1", "custom.switch_2"], CONF_TRANSPORT: "generic"}
    }
    mock_context.deliveries = build_delivery_from_config(delivery, mock_hass, mock_context, mock_people_registry)
    uut = Notification(mock_context, mock_people_registry, "testing 123")
    generic = GenericTransport(mock_hass, mock_context, mock_people_registry, delivery)
    await generic.initialize()
    recipients: list[Target] = uut.generate_recipients("chatty", generic)
    assert recipients[0].entity_ids == ["custom.light_1", "custom.switch_2"]


async def test_generate_recipients_from_recipients(
    mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry
) -> None:
    delivery = {
        "chatty": {
            CONF_ACTION: "custom.tweak",
            CONF_TARGET: {"entity_id": ["custom.light_1"], "person_id": ["person.new_home_owner"]},
            CONF_TRANSPORT: "generic",
            CONF_OPTIONS: {OPTION_TARGET_CATEGORIES: ["entity_id", "other_id"]},
        }
    }
    mock_people_registry.people = {
        "person.new_home_owner": {
            CONF_PERSON: "person.new_home_owner",
            CONF_DELIVERY: {"chatty": {CONF_TARGET: ["@foo", "@bar"]}},
        }
    }
    mock_context.deliveries = build_delivery_from_config(delivery, mock_hass, mock_context, mock_people_registry)
    uut = Notification(mock_context, mock_people_registry, "testing 123")
    generic = GenericTransport(mock_hass, mock_context, mock_people_registry, delivery)
    await generic.initialize()
    recipients: list[Target] = uut.generate_recipients("chatty", generic)
    assert recipients[0].entity_ids == ["custom.light_1"]
    assert recipients[0].other_ids == ["@foo", "@bar"]


async def test_explicit_recipients_only_restricts_people_targets(
    mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry
) -> None:
    delivery = {
        "chatty": {CONF_ACTION: "notify.slackity", CONF_TARGET: ["chan1", "chan2"], CONF_TRANSPORT: "generic"},
        "mail": {CONF_ACTION: "notify.smtp", CONF_TRANSPORT: "email"},
    }
    mock_people_registry.people = {
        "person.bob": {CONF_PERSON: "person.bob", CONF_EMAIL: "bob@test.com"},
        "person.jane": {CONF_PERSON: "person.jane", CONF_EMAIL: "jane@test.com"},
    }
    mock_context.deliveries = build_delivery_from_config(delivery, mock_hass, mock_context, mock_people_registry)
    uut = Notification(mock_context, mock_people_registry, "testing 123")
    generic = GenericTransport(mock_hass, mock_context, mock_people_registry, delivery)
    await generic.initialize()
    recipients: list[Target] = uut.generate_recipients("chatty", generic)
    assert recipients[0].other_ids == ["chan1", "chan2"]
    bundles = uut.generate_envelopes("chatty", generic, recipients)
    assert bundles == [Envelope("chatty", uut, target=Target(["chan1", "chan2"]))]
    email = EmailTransport(mock_hass, mock_context, mock_people_registry, delivery)
    await email.initialize()
    recipients = uut.generate_recipients("mail", email)
    assert recipients[0].email == ["bob@test.com", "jane@test.com"]
    bundles = uut.generate_envelopes("mail", email, recipients)
    assert bundles == [Envelope("mail", uut, target=Target(["bob@test.com", "jane@test.com"]))]


async def test_filter_recipients(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    uut = Notification(mock_context, mock_people_registry, "testing 123")
    await uut.initialize()

    assert len(uut.filter_people_by_occupancy("all_in")) == 0
    assert len(uut.filter_people_by_occupancy("all_out")) == 0
    assert len(uut.filter_people_by_occupancy("any_in")) == 2
    assert len(uut.filter_people_by_occupancy("any_out")) == 2
    assert len(uut.filter_people_by_occupancy("only_in")) == 1
    assert len(uut.filter_people_by_occupancy("only_out")) == 1

    assert {r["person"] for r in uut.filter_people_by_occupancy("only_out")} == {"person.new_home_owner"}
    assert {r["person"] for r in uut.filter_people_by_occupancy("only_in")} == {"person.bidey_in"}


async def test_build_targets_for_simple_case(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    transport = GenericTransport(mock_context.hass, mock_context, mock_people_registry, {})
    await transport.initialize()
    # mock_context.deliveries={'testy':Delivery("testy",{},transport)}
    uut = Notification(mock_context, mock_people_registry, "testing 123")
    recipients: list[Target] = uut.generate_recipients("", transport)
    bundles = uut.generate_envelopes("", transport, recipients)
    assert bundles == [Envelope("", uut)]


async def test_dict_of_delivery_tuning_does_not_restrict_deliveries(
    mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry
) -> None:
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}
    uut = Notification(mock_context, mock_people_registry, "testing 123", action_data={CONF_DELIVERY: {"mobile": {}}})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile")


async def test_snapshot_url(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    uut = Notification(
        mock_context,
        mock_people_registry,
        "testing 123",
        action_data={CONF_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/my_local_image"}},
    )
    await uut.initialize()
    original_image_path: Path = Path(tempfile.gettempdir()) / "image_a.jpg"
    with patch(
        "custom_components.supernotify.media_grab.snapshot_from_url", return_value=original_image_path
    ) as mock_snapshot:
        retrieved_image_path = await grab_image(uut, "example", uut.context)
        assert retrieved_image_path == original_image_path
        assert mock_snapshot.called
        mock_snapshot.reset_mock()
        retrieved_image_path = await grab_image(uut, "example", uut.context)
        assert retrieved_image_path == original_image_path
        # notification caches image for multiple deliveries
        mock_snapshot.assert_not_called()


async def test_camera_entity(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    uut = Notification(
        mock_context,
        mock_people_registry,
        "testing 123",
        action_data={CONF_MEDIA: {ATTR_MEDIA_CAMERA_ENTITY_ID: "camera.lobby"}},
    )
    await uut.initialize()
    original_image_path: Path = Path(tempfile.gettempdir()) / "image_b.jpg"
    with patch("custom_components.supernotify.media_grab.snap_camera", return_value=original_image_path) as mock_snap_cam:
        retrieved_image_path = await grab_image(uut, "example", uut.context)
        assert retrieved_image_path == original_image_path
        assert mock_snap_cam.called
        mock_snap_cam.reset_mock()
        retrieved_image_path = await grab_image(uut, "example", uut.context)
        assert retrieved_image_path == original_image_path
        # notification caches image for multiple deliveries
        mock_snap_cam.assert_not_called()


async def test_message_usage(
    mock_hass: HomeAssistant, mock_context: Context, mock_transport: Transport, mock_people_registry: PeopleRegistry
) -> None:
    delivery = Mock(spec=Delivery, title=None, message=None, selection=DELIVERY_SELECTION_IMPLICIT)
    mock_context.deliveries = {"push": delivery}
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["push"]}

    uut = Notification(mock_context, mock_people_registry, "testing 123", title="the big title")
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") == "the big title"

    delivery.option_str.return_value = MessageOnlyPolicy.USE_TITLE
    uut = Notification(mock_context, mock_people_registry, "testing 123", title="the big title")
    await uut.initialize()
    assert uut.message("push") == "the big title"
    assert uut.title("push") is None

    delivery.option_str.return_value = MessageOnlyPolicy.USE_TITLE
    uut = Notification(mock_context, mock_people_registry, "testing 123")
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") is None

    delivery.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE
    uut = Notification(mock_context, mock_people_registry, "testing 123", title="the big title")
    await uut.initialize()
    assert uut.message("push") == "the big title testing 123"
    assert uut.title("push") is None

    delivery.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE
    uut = Notification(mock_context, mock_people_registry, "testing 123")
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") is None


async def test_merge(mock_hass: HomeAssistant, mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    mock_context.scenario_registry.scenarios = {
        "Alarm": Scenario("Alarm", {"media": {"jpeg_opts": {"quality": 30}, "snapshot_url": "/bar/789"}}, mock_hass)
    }
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}
    uut = Notification(
        mock_context,
        mock_people_registry,
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
