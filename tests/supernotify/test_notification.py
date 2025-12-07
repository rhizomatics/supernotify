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
    CONF_SELECTION_RANK,
    CONF_TARGET_USAGE,
    CONF_TITLE,
    CONF_TRANSPORT,
    DELIVERY_SELECTION_EXPLICIT,
    DELIVERY_SELECTION_IMPLICIT,
    OPTION_TARGET_CATEGORIES,
    TRANSPORT_EMAIL,
    TRANSPORT_GENERIC,
    TRANSPORT_MOBILE_PUSH,
    SelectionRank,
)
from custom_components.supernotify.context import Context
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.hass_api import HomeAssistantAPI
from custom_components.supernotify.media_grab import grab_image
from custom_components.supernotify.model import MessageOnlyPolicy, Target
from custom_components.supernotify.notification import DebugTrace, Notification
from custom_components.supernotify.people import PeopleRegistry
from custom_components.supernotify.scenario import Scenario
from custom_components.supernotify.transports.email import EmailTransport

from .hass_setup_lib import TestingContext


async def test_simple_create() -> None:
    ctx = TestingContext(
        deliveries={
            "mobile": {CONF_TITLE: "mobile notification", CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH},
            "plain_email": {CONF_ACTION: "notify.smtp", CONF_TRANSPORT: TRANSPORT_EMAIL},
        },
    )
    await ctx.test_initialize()

    # mock_context.delivery_registry.implicit_delivery_names=["plain_email", "mobile"]
    uut = Notification(ctx, "testing 123")
    await uut.initialize()
    assert uut.enabled_scenarios == {}
    assert uut.applied_scenario_names == []
    assert uut.target is None
    assert uut.message("plain_email") == "testing 123"
    assert uut.title("mobile") == "mobile notification"
    assert uut.priority == "medium"
    assert uut.delivery_overrides == {}
    assert uut.delivery_selection == DELIVERY_SELECTION_IMPLICIT
    assert uut.recipients_override is None
    assert uut.selected_delivery_names == unordered(["plain_email", "mobile", "DEFAULT_notify_entity"])


async def test_explicit_delivery(mock_hass: HomeAssistant, mock_context: Context, deliveries: dict[str, Delivery]) -> None:
    mock_context.delivery_registry.implicit_deliveries = deliveries.values()  # type: ignore

    # string forces explicit selection
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={CONF_DELIVERY: "mobile"},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert uut.selected_delivery_names == ["mobile"]

    # list forces explicit selection
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={CONF_DELIVERY: ["mobile", "chime"]},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert uut.selected_delivery_names == unordered(["mobile", "chime"])

    # dict doesn't force explicit selection
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile": {CONF_DATA: {"foo": "bar"}}}},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_IMPLICIT
    assert uut.selected_delivery_names == unordered(["mobile", "plain_email", "chime"])


async def test_scenario_delivery(mock_context: Context, mock_scenario: Scenario, deliveries: dict[str, Delivery]) -> None:
    mock_context.delivery_registry.implicit_deliveries = deliveries.values()  # type: ignore
    mock_context.scenario_registry.scenarios = {"mockery": mock_scenario}
    uut = Notification(mock_context, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime")


async def test_explicit_list_of_deliveries(mock_context: Context) -> None:
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}

    uut = Notification(mock_context, "testing 123", action_data={CONF_DELIVERY: "mobile"})
    await uut.initialize()
    assert uut.selected_delivery_names == ["mobile"]


async def test_action_data_disable_delivery(
    mock_context: Context, mock_scenario: Scenario, deliveries: dict[str, Delivery]
) -> None:
    mock_context.delivery_registry.implicit_deliveries = deliveries.values()  # type: ignore
    mock_context.scenario_registry.scenarios = {"mockery": mock_scenario}
    uut = Notification(
        mock_context, "testing 123", action_data={"delivery": {"mobile": {"enabled": False}}, ATTR_SCENARIOS_APPLY: "mockery"}
    )
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "chime")


async def test_generate_recipients_from_entities() -> None:
    ctx = TestingContext(
        deliveries={
            "chatty": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light_1", "custom.switch_2"],
                CONF_TRANSPORT: "generic",
            }
        }
    )
    await ctx.test_initialize()
    delivery = ctx.delivery("chatty")

    uut = Notification(ctx, "testing 123")

    recipients: list[Target] = uut.generate_recipients(delivery)
    assert recipients[0].entity_ids == ["custom.light_1", "custom.switch_2"]


async def test_generate_recipients_from_recipients() -> None:
    ctx = TestingContext(
        recipients=[
            {
                CONF_PERSON: "person.new_home_owner",
                CONF_TARGET: ["@foo", "@bar"],
                CONF_DELIVERY: {"chatty": {CONF_TARGET: ["@fee", "@fum"]}},
            }
        ],
        deliveries={
            "chatty": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: {"entity_id": ["custom.light_1"], "person_id": ["person.new_home_owner"]},
                CONF_TARGET_USAGE: "merge_delivery",
                CONF_TRANSPORT: "generic",
                CONF_OPTIONS: {OPTION_TARGET_CATEGORIES: ["entity_id", "_UNKNOWN_"]},
            }
        },
    )
    await ctx.test_initialize()
    delivery = ctx.delivery("chatty")

    uut = Notification(ctx, "testing 123")

    recipients: list[Target] = uut.generate_recipients(delivery)
    assert recipients[0].entity_ids == ["custom.light_1"]
    assert recipients[0].custom_ids("_UNKNOWN_") == ["@foo", "@bar", "@fee", "@fum"]


async def test_explicit_recipients_only_restricts_people_targets() -> None:
    ctx = TestingContext(
        recipients=[
            {CONF_PERSON: "person.bob", CONF_EMAIL: "bob@test.com"},
            {CONF_PERSON: "person.jane", CONF_EMAIL: "jane@test.com"},
        ],
        deliveries={
            "chatty": {
                CONF_ACTION: "notify.slackity",
                CONF_TARGET: ["chan1", "chan2"],
                CONF_TARGET_USAGE: "merge_always",
                CONF_TRANSPORT: "generic",
                CONF_OPTIONS: {OPTION_TARGET_CATEGORIES: ["entity_id", "_UNKNOWN_"]},
            },
            "mail": {CONF_ACTION: "notify.smtp", CONF_TRANSPORT: "email"},
        },
    )
    await ctx.test_initialize()
    delivery = ctx.delivery("chatty")
    generic = ctx.transport(TRANSPORT_GENERIC)

    uut = Notification(ctx, "testing 123")

    recipients: list[Target] = uut.generate_recipients(delivery)
    assert recipients[0].custom_ids("_UNKNOWN_") == ["chan1", "chan2"]
    bundles = uut.generate_envelopes(delivery, recipients)
    assert bundles == [
        Envelope(Delivery("chatty", ctx.delivery_config("chatty"), generic), uut, target=Target(["chan1", "chan2"]))
    ]
    email = EmailTransport(ctx)
    await email.initialize()
    delivery = ctx.delivery("mail")
    recipients = uut.generate_recipients(delivery)
    assert recipients[0].email == ["bob@test.com", "jane@test.com"]
    bundles = uut.generate_envelopes(delivery, recipients)
    assert bundles == [
        Envelope(Delivery("mail", ctx.delivery_config("mail"), email), uut, target=Target(["bob@test.com", "jane@test.com"]))
    ]


async def test_build_targets_for_simple_case() -> None:
    ctx = TestingContext()
    await ctx.test_initialize()
    generic = ctx.transport(TRANSPORT_GENERIC)
    delivery = Delivery("simple", {}, generic)

    # mock_context.deliveries={'testy':Delivery("testy",{},transport)}
    uut = Notification(ctx, "testing 123")
    recipients: list[Target] = uut.generate_recipients(delivery)
    bundles = uut.generate_envelopes(delivery, recipients)
    assert bundles == [Envelope(Delivery("simple", {}, generic), uut)]


async def test_dict_of_delivery_tuning_does_not_restrict_deliveries(
    mock_context: Context, deliveries: dict[str, Delivery]
) -> None:
    ctx = TestingContext()
    await ctx.test_initialize()
    mock_context.delivery_registry.implicit_deliveries = deliveries.values()  # type: ignore
    uut = Notification(mock_context, "testing 123", action_data={CONF_DELIVERY: {"mobile": {}}})
    await uut.initialize()
    assert uut.selected_delivery_names == unordered("plain_email", "mobile", "chime")


async def test_snapshot_url(mock_context: Context, mock_people_registry: PeopleRegistry) -> None:
    uut = Notification(
        mock_context,
        "testing 123",
        action_data={CONF_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/my_local_image"}},
    )
    await uut.initialize()
    original_image_path: Path = Path(tempfile.gettempdir()) / "image_a.jpg"
    with patch("custom_components.supernotify.media_grab.snapshot_from_url", return_value=original_image_path) as mock_snapshot:
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


async def test_message_usage(mock_context: Context) -> None:
    delivery = Mock(spec=Delivery, title=None, message=None, selection=DELIVERY_SELECTION_IMPLICIT)
    mock_context.delivery_registry.deliveries = {"push": delivery}
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["push"]}

    uut = Notification(mock_context, "testing 123", title="the big title")
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") == "the big title"

    delivery.option_str.return_value = MessageOnlyPolicy.USE_TITLE
    uut = Notification(mock_context, "testing 123", title="the big title")
    await uut.initialize()
    assert uut.message("push") == "the big title"
    assert uut.title("push") is None

    delivery.option_str.return_value = MessageOnlyPolicy.USE_TITLE
    uut = Notification(mock_context, "testing 123")
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") is None

    delivery.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE
    uut = Notification(mock_context, "testing 123", title="the big title")
    await uut.initialize()
    assert uut.message("push") == "the big title testing 123"
    assert uut.title("push") is None

    delivery.option_str.return_value = MessageOnlyPolicy.COMBINE_TITLE
    uut = Notification(mock_context, "testing 123")
    await uut.initialize()
    assert uut.message("push") == "testing 123"
    assert uut.title("push") is None


async def test_merge(mock_hass_api: HomeAssistantAPI, mock_context: Context) -> None:
    mock_context.scenario_registry.scenarios = {
        "Alarm": Scenario("Alarm", {"media": {"jpeg_opts": {"quality": 30}, "snapshot_url": "/bar/789"}}, mock_hass_api)
    }
    mock_context.scenario_registry.delivery_by_scenario = {"DEFAULT": ["plain_email", "mobile"], "Alarm": ["chime"]}
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


async def test_delivery_selection_order() -> None:
    ctx = TestingContext(
        deliveries={
            "fallback": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.LAST,
            },
            "eager": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light1"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.FIRST,
            },
            "whatever": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light2"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.ANY,
            },
            "or_whatever": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light3"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.ANY,
            },
            "naturally_last": {CONF_TARGET: ["notify.me"], CONF_TRANSPORT: "notify_entity"},
        }
    )
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123")
    await uut.initialize()

    assert len(uut.selected_delivery_names) == 5
    assert uut.selected_delivery_names[0] == "eager"
    assert uut.selected_delivery_names[1:3] == unordered("whatever", "or_whatever")
    assert uut.selected_delivery_names[-2:] == unordered("fallback", "naturally_last")


def test_debug_trace_for_targets():
    uut = DebugTrace("message", "title", {}, {})
    uut.record_target("omni", "stage_1", Target(["switch.hall", "joe@mctoe.com"]))
    uut.record_target("omni", "stage_2", Target(["switch.hall", "joe@mctoe.com"]))
    uut.record_target("omni", "stage_3", Target(["joe@mctoe.com"]))
    uut.record_target("omni", "stage_4", Target(["joe@mctoe.com", "home@24acacia.ave"]))
    uut.record_target("omni", "stage_5", Target())

    assert len(uut.contents()["resolved"]["omni"]) == 5
    assert uut.contents()["resolved"]["omni"]["stage_1"] == {"email": ["joe@mctoe.com"], "entity_id": ["switch.hall"]}
    assert uut.contents()["resolved"]["omni"]["stage_2"] == "NO_CHANGE"
    assert uut.contents()["resolved"]["omni"]["stage_3"] == {"email": ["joe@mctoe.com"]}
    assert uut.contents()["resolved"]["omni"]["stage_4"] == {"email": ["joe@mctoe.com", "home@24acacia.ave"]}
    assert uut.contents()["resolved"]["omni"]["stage_5"] == {}
