import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.const import CONF_ACTION, CONF_EMAIL, CONF_ENABLED, CONF_TARGET
from pytest_unordered import unordered

from custom_components.supernotify.const import (
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_PRIORITY,
    ATTR_SCENARIOS_APPLY,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_MEDIA,
    CONF_MOBILE_APP_ID,
    CONF_MOBILE_DEVICES,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_SELECTION,
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
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.media_grab import snap_notification_image
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import SelectionRank
from custom_components.supernotify.transports.email import EmailTransport
from tests.components.supernotify.hass_setup_lib import TestingContext, first_envelope

DELIVERIES = """
plain_email:
    transport: email
    action: notify.smtp
mobile:
    transport: mobile_push
chime:
    transport: chime
"""
TRANSPORTS = """
notify_entity:
    enabled: false
"""
RECIPIENTS = """
    - person: person.joe_mcphee
      email: joe.mcphee@home.mail.net
      phone_number: "+3294924848"
      mobile_devices:
        - mobile_app_id: mobile_app_joe_nokia
    - person: person.jabilee_sokata
      email: jab@sokata.family.net
"""


async def test_simple_create() -> None:
    ctx = TestingContext(
        deliveries={
            "mobile": {CONF_TITLE: "mobile notification", CONF_TRANSPORT: TRANSPORT_MOBILE_PUSH},
            "plain_email": {CONF_ACTION: "notify.smtp", CONF_TRANSPORT: TRANSPORT_EMAIL},
        },
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123")
    await uut.initialize()
    assert uut.enabled_scenarios == {}
    assert uut.applied_scenario_names == []
    assert uut._target is None
    assert uut.priority == "medium"
    assert uut.delivery_overrides == {}
    assert uut.delivery_selection == DELIVERY_SELECTION_IMPLICIT
    assert list(uut.selected_deliveries) == unordered(["plain_email", "mobile", "DEFAULT_notify_entity"])


async def test_explicit_delivery() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()

    # string forces explicit selection
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: "mobile"},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert list(uut.selected_deliveries) == ["mobile"]

    # list forces explicit selection
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: ["mobile", "chime"]},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert list(uut.selected_deliveries) == unordered(["mobile", "chime"])

    # dict doesn't force explicit selection
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile": {CONF_DATA: {"foo": "bar"}}}},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_IMPLICIT
    assert list(uut.selected_deliveries) == unordered(["mobile", "plain_email", "chime"])


async def test_channel_specific_message() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        recipients=RECIPIENTS,
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile": {CONF_DATA: {"message": "buzz", "title": "HASS"}}}},
    )
    await uut.initialize()
    await uut.deliver()
    mobile_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "mobile")
    email_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "plain_email")

    assert mobile_envelope.message == "buzz"
    assert mobile_envelope.title == "HASS"

    assert email_envelope.message == "testing 123"
    assert email_envelope.title is None


async def test_channel_transport_override() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        recipients=RECIPIENTS,
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile_push": {CONF_DATA: {"message": "buzz", "title": "HASS"}}}},
    )
    await uut.initialize()
    await uut.deliver()
    mobile_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "mobile")
    email_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "plain_email")

    assert mobile_envelope.message == "buzz"
    assert mobile_envelope.title == "HASS"

    assert email_envelope.message == "testing 123"
    assert email_envelope.title is None


async def test_custom_priority() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={ATTR_PRIORITY: "most_urgent"})
    await uut.initialize()
    assert uut.priority == "most_urgent"


async def test_bad_priority() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()

    with pytest.raises(vol.Invalid):
        Notification(ctx, "testing 123", action_data={ATTR_PRIORITY: {"pri": 9, "desc": "most_urgent"}})


async def test_scenario_delivery_no_change() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, scenarios={"mockery": {}})
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("plain_email", "mobile", "chime")


async def test_scenario_delivery_disable() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES, transports=TRANSPORTS, scenarios={"mockery": {"delivery": {"chime": {"enabled": False}}}}
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("plain_email", "mobile")


async def test_scenario_delivery_enable() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES, transports=TRANSPORTS, scenarios={"mockery": {"delivery": {"chime": {"enabled": True}}}}
    )
    await ctx.test_initialize()
    ctx.delivery_registry.deliveries["chime"].enabled = False

    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("plain_email", "mobile", "chime")


async def test_explicit_list_of_deliveries() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: "mobile"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == ["mobile"]


async def test_action_data_disable_delivery() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, scenarios={"mockery": {}})
    await ctx.test_initialize()

    uut = Notification(
        ctx, "testing 123", action_data={"delivery": {"mobile": {"enabled": False}}, ATTR_SCENARIOS_APPLY: "mockery"}
    )
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("plain_email", "chime")


async def test_generate_targets_from_entities() -> None:
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

    recipients: list[Target] = uut.generate_targets(delivery)
    assert recipients[0].entity_ids == ["custom.light_1", "custom.switch_2"]


async def test_generate_targets_from_recipients() -> None:
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

    recipients: list[Target] = uut.generate_targets(delivery)
    assert recipients[0].entity_ids == ["custom.light_1"]
    assert recipients[0].custom_ids("_UNKNOWN_") == ["@foo", "@bar", "@fee", "@fum"]


async def test_select_recipient_deliveries() -> None:
    ctx = TestingContext(
        recipients=[
            {
                CONF_PERSON: "person.new_home_owner",
                CONF_EMAIL: "owner@mctest.org",
                CONF_MOBILE_DEVICES: [{CONF_MOBILE_APP_ID: "mobile_app_joephone"}],
                CONF_DELIVERY: {"chatty": {CONF_ENABLED: True}},
            },
            {
                CONF_PERSON: "person.kid_no_3",
                CONF_EMAIL: "kid3@mctest.org",
                CONF_MOBILE_DEVICES: [{CONF_MOBILE_APP_ID: "mobile_app_kidphone"}],
            },
        ],
        deliveries={"chatty": {CONF_TRANSPORT: "email", CONF_ACTION: "notify.smtp", CONF_SELECTION: ["explicit"]}},
        services={"notify": ["smtp", "mobile_app_kidphone", "mobile_app_joephone"]},
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123")
    await uut.initialize()
    await uut.deliver()
    assert first_envelope(uut, "DEFAULT_mobile_push").target.mobile_app_ids == ["mobile_app_joephone", "mobile_app_kidphone"]
    assert first_envelope(uut, "chatty").target.email == ["owner@mctest.org"]  # type: ignore


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

    recipients: list[Target] = uut.generate_targets(delivery)
    assert recipients[0].custom_ids("_UNKNOWN_") == ["chan1", "chan2"]
    bundles = uut.generate_envelopes(delivery, recipients)
    assert bundles == [
        Envelope(Delivery("chatty", ctx.delivery_config("chatty"), generic), uut, target=Target(["chan1", "chan2"]))
    ]
    email = EmailTransport(ctx)
    await email.initialize()
    delivery = ctx.delivery("mail")
    recipients = uut.generate_targets(delivery)
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

    uut = Notification(ctx, "testing 123")
    recipients: list[Target] = uut.generate_targets(delivery)
    bundles = uut.generate_envelopes(delivery, recipients)
    assert bundles == [Envelope(Delivery("simple", {}, generic), uut)]


async def test_dict_of_delivery_tuning_does_not_restrict_deliveries() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: {"mobile": {}}})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("plain_email", "mobile", "chime")


async def test_snapshot_url() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_MEDIA: {ATTR_MEDIA_SNAPSHOT_URL: "/my_local_image"}},
    )
    await uut.initialize()
    original_image_path: Path = Path(tempfile.gettempdir()) / "image_a.jpg"
    with patch("custom_components.supernotify.media_grab.snapshot_from_url", return_value=original_image_path) as mock_snapshot:
        retrieved = await snap_notification_image(uut, uut.context)
        assert retrieved == original_image_path
        assert mock_snapshot.called
        mock_snapshot.reset_mock()
        # second call returns cached raw path without re-fetching the URL
        retrieved2 = await snap_notification_image(uut, uut.context)
        assert retrieved2 == original_image_path
        mock_snapshot.assert_not_called()


async def test_camera_entity() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_MEDIA: {ATTR_MEDIA_CAMERA_ENTITY_ID: "camera.lobby"}},
    )
    await uut.initialize()
    original_image_path: Path = Path(tempfile.gettempdir()) / "image_b.jpg"
    with patch("custom_components.supernotify.media_grab.snap_camera", return_value=original_image_path) as mock_snap_cam:
        retrieved = await snap_notification_image(uut, uut.context)
        assert retrieved == original_image_path
        assert mock_snap_cam.called
        mock_snap_cam.reset_mock()
        # second call returns cached raw path without re-snapping the camera
        retrieved2 = await snap_notification_image(uut, uut.context)
        assert retrieved2 == original_image_path
        mock_snap_cam.assert_not_called()


async def test_deliver_skips_image_grab_when_no_delivery_uses_camera() -> None:
    """Capturing an image has real overhead (a service call, then polling for the file
    to appear) that must not be paid when no selected delivery would even use it — here
    only chime (no SNAPSHOT_IMAGE feature) is selected, despite camera media being present."""
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()
    uut = Notification(
        ctx,
        "testing 123",
        action_data={
            CONF_DELIVERY: ["chime"],
            CONF_MEDIA: {ATTR_MEDIA_CAMERA_ENTITY_ID: "camera.lobby"},
        },
    )
    await uut.initialize()
    with patch("custom_components.supernotify.notification._snap_notification_image", new_callable=AsyncMock) as mock_snap:
        await uut.deliver()
    mock_snap.assert_not_called()


async def test_deliver_grabs_image_when_a_delivery_uses_camera() -> None:
    """mobile (mobile_push) supports SNAPSHOT_IMAGE, so with camera media present the
    image grab must be kicked off."""
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS)
    await ctx.test_initialize()
    uut = Notification(
        ctx,
        "testing 123",
        action_data={
            CONF_DELIVERY: ["mobile"],
            CONF_MEDIA: {ATTR_MEDIA_CAMERA_ENTITY_ID: "camera.lobby"},
        },
    )
    await uut.initialize()
    with patch(
        "custom_components.supernotify.notification._snap_notification_image", new_callable=AsyncMock, return_value=None
    ) as mock_snap:
        await uut.deliver()
    mock_snap.assert_called_once()


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

    assert len(list(uut.selected_deliveries)) == 6
    assert next(iter(uut.selected_deliveries)) == "eager"
    assert list(uut.selected_deliveries)[-2:] == unordered("fallback", "naturally_last")
    assert list(uut.selected_deliveries)[1:4] == unordered("DEFAULT_mobile_push", "whatever", "or_whatever")


async def test_convert_notify_entities() -> None:
    ctx = TestingContext(recipients=[{CONF_PERSON: "person.alice"}])
    await ctx.test_initialize()
    ctx.people_registry.people["person.alice"].notify_entity_id = "notify.recipient_alice"
    uut = Notification(ctx, "testing 123")

    converted = uut.convert_notify_entities(["notify.recipient_alice", "media_player.kitchen"])

    assert converted == ["person.alice", "media_player.kitchen"]


async def test_convert_notify_entities_ignores_unrecognized_notify_entities() -> None:
    ctx = TestingContext()
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123")

    converted = uut.convert_notify_entities(["notify.some_other_integration", "media_player.kitchen"])

    assert converted == ["notify.some_other_integration", "media_player.kitchen"]


async def test_convert_notify_entities_handles_person_entity_in_dict_target() -> None:
    """Reproduces a crash reported from a real supernotify.notify call: a dict-shaped target
    (from Home Assistant's target selector, e.g. {"entity_id": ["person.jey"]}) was passed into
    ensure_list()/`in` checks designed for a flat string/list target, raising TypeError:
    unhashable type: 'dict' once ensure_list() wrapped the whole dict as a single element.

    Fixing just the crash isn't enough though: Home Assistant's target selector always puts a
    picked person entity under `entity_id`, regardless of its domain, but Target()'s dict branch
    treats each key as already resolved to the right category - and its entity_id category
    explicitly excludes the person domain (see Target.is_entity_id) - so an unconverted person
    entity would be silently dropped from targeting rather than raising. It has to be moved to
    `person_id` here, same as it would be if passed as a flat string/list target instead.
    """
    ctx = TestingContext(recipients=[{CONF_PERSON: "person.alice"}])
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123")

    converted = uut.convert_notify_entities({"entity_id": ["person.alice", "media_player.kitchen"]})

    assert converted == {"entity_id": ["media_player.kitchen"], "person_id": ["person.alice"]}


async def test_convert_notify_entities_resolves_recipient_notify_entity_in_dict_target() -> None:
    """A supernotify.notify target picked as one of supernotify's own notify.recipient_* entities
    resolves to the underlying person, same as the flat string/list case - avoiding a round trip
    back through NotifyEntityTransport's notify.send_message. A genuine other-integration notify
    entity (e.g. notify.some_other_integration) is left in entity_id for that transport to handle."""
    ctx = TestingContext(recipients=[{CONF_PERSON: "person.alice"}])
    await ctx.test_initialize()
    ctx.people_registry.people["person.alice"].notify_entity_id = "notify.recipient_alice"
    uut = Notification(ctx, "testing 123")

    converted = uut.convert_notify_entities({"entity_id": ["notify.recipient_alice", "notify.some_other_integration"]})

    assert converted == {"entity_id": ["notify.some_other_integration"], "person_id": ["person.alice"]}


async def test_notification_accepts_dict_shaped_target_without_crashing() -> None:
    ctx = TestingContext(recipients=[{CONF_PERSON: "person.alice"}])
    await ctx.test_initialize()

    uut = Notification(ctx, "a wee test", target={"entity_id": ["person.alice"]})

    assert uut._target is not None
    assert uut._target.person_ids == ["person.alice"]
