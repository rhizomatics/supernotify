import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol
from homeassistant.const import CONF_ACTION, CONF_EMAIL, CONF_ENABLED, CONF_TARGET
from homeassistant.core import Context as HAContext
from pytest_asyncio import fixture
from pytest_unordered import unordered

from custom_components.supernotify.const import (
    ATTR_MEDIA_CAMERA_ENTITY_ID,
    ATTR_MEDIA_SNAPSHOT_URL,
    ATTR_PRIORITY,
    ATTR_SCENARIOS_APPLY,
    CONF_DATA,
    CONF_DELIVERY,
    CONF_INCLUSION,
    CONF_MEDIA,
    CONF_MOBILE_APP_ID,
    CONF_MOBILE_DEVICES,
    CONF_OPTIONS,
    CONF_PERSON,
    CONF_PHONE_NUMBER,
    CONF_SELECTION_RANK,
    CONF_TARGET_USAGE,
    CONF_TRANSPORT,
    DELIVERY_SELECTION_EXPLICIT,
    DELIVERY_SELECTION_IMPLICIT,
    INCLUSION_DEFAULT,
    TRANSPORT_GENERIC,
    TRANSPORT_SMS,
)
from custom_components.supernotify.delivery import Delivery
from custom_components.supernotify.engine import TRANSPORTS as ALL_TRANSPORT_TYPES
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.media_grab import snap_notification_image
from custom_components.supernotify.model import Target
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.options import OPTION_TARGET_CATEGORIES
from custom_components.supernotify.people import RecipientNotifyEntity
from custom_components.supernotify.schema import DeliveryOutcome, SelectionRank
from custom_components.supernotify.transports.email import EmailTransport
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from custom_components.supernotify.transports.notify_entity import NotifyEntityTransport
from custom_components.supernotify.transports.sms import SMSTransport
from tests.components.supernotify.hass_setup_lib import TestingContext, first_envelope

DELIVERIES = """
chime:
    transport: chime
    inclusion:
    - default
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
MOCK_SERVICES: dict[str, list[str] | list[dict[str, Any]]] = {
    "notify": [{"action": "mobile_app_joe_nokia"}, {"action": "send", "module": "homeassistant.components.smtp.notify"}]
}


async def test_simple_create() -> None:
    ctx = TestingContext(
        viable_transport_types=[MobilePushTransport, EmailTransport, NotifyEntityTransport], services=MOCK_SERVICES
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
    assert list(uut.selected_deliveries) == unordered(["email", "mobile_push", "notify_entity"])


async def test_legacy_default_prefixed_delivery_name_resolves_to_current() -> None:
    """Backward compatibility: an old automation referencing 'delivery: DEFAULT_notify_entity'
    (the pre-rename auto-configured name) still resolves to the current 'notify_entity'."""
    ctx = TestingContext()
    await ctx.test_initialize()
    assert "notify_entity" in ctx.delivery_registry.deliveries

    uut = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: "DEFAULT_notify_entity"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == ["notify_entity"]


async def test_explicit_delivery() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES, services=MOCK_SERVICES
    )
    await ctx.test_initialize()

    # string forces explicit selection
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: "mobile_push"},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert list(uut.selected_deliveries) == ["mobile_push"]

    # list forces explicit selection
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: ["mobile_push", "chime"]},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_EXPLICIT
    assert list(uut.selected_deliveries) == unordered(["mobile_push", "chime"])

    # dict doesn't force explicit selection
    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile_push": {CONF_DATA: {"foo": "bar"}}}},
    )
    await uut.initialize()
    assert uut.delivery_selection == DELIVERY_SELECTION_IMPLICIT
    assert list(uut.selected_deliveries) == unordered(["mobile_push", "email", "chime"])


async def test_channel_specific_message() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        recipients=RECIPIENTS,
        viable_transport_types=[MobilePushTransport, EmailTransport, NotifyEntityTransport],
        services=MOCK_SERVICES,
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile_push": {CONF_DATA: {"message": "buzz", "title": "HASS"}}}},
    )
    await uut.initialize()
    await uut.deliver()
    mobile_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "mobile_push")
    email_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "email")

    assert mobile_envelope.message == "buzz"
    assert mobile_envelope.title == "HASS"

    assert email_envelope.message == "testing 123"
    assert email_envelope.title is None


async def test_channel_transport_override() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        recipients=RECIPIENTS,
        viable_transport_types=[MobilePushTransport, EmailTransport, NotifyEntityTransport],
        services=MOCK_SERVICES,
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        action_data={CONF_DELIVERY: {"mobile_push": {CONF_DATA: {"message": "buzz", "title": "HASS"}}}},
    )
    await uut.initialize()
    await uut.deliver()
    mobile_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "mobile_push")
    email_envelope = next(e for e in uut.delivered_envelopes if e.delivery_name == "email")

    assert mobile_envelope.message == "buzz"
    assert mobile_envelope.title == "HASS"

    assert email_envelope.message == "testing 123"
    assert email_envelope.title is None


async def test_unassigned_targets_reported_in_archive() -> None:
    """A target value with a recognisable shape (phone) that no configured delivery

    declares (plain_email wants email, mobile wants mobile_app_id, chime wants entities/
    device_id) never lands in any envelope - it should show up as `unassigned_targets`
    in the archived contents, grouped by category, distinct from `uncategorized_targets`
    (which is for values with no recognisable shape at all).
    """
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        recipients=RECIPIENTS,
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", target=["+3294924848"])
    await uut.initialize()
    await uut.deliver()

    assert uut.contents()["unassigned_targets"] == {"phone": ["+3294924848"]}


async def test_call_transport_records_delivery_exception() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: "mobile_push"})
    await uut.initialize()
    delivery = ctx.delivery("mobile_push")

    with patch.object(delivery, "evaluate_conditions", side_effect=RuntimeError("boom")):
        await uut.deliver()

    assert "mobile_push" in uut.delivery_exceptions
    assert "boom" in uut.delivery_exceptions["mobile_push"][0]
    assert uut.outcome() == DeliveryOutcome.ERROR


async def test_custom_priority() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={ATTR_PRIORITY: "most_urgent"})
    await uut.initialize()
    assert uut.priority == "most_urgent"


async def test_bad_priority() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
    await ctx.test_initialize()

    with pytest.raises(vol.Invalid):
        Notification(ctx, "testing 123", action_data={ATTR_PRIORITY: {"pri": 9, "desc": "most_urgent"}})


async def test_scenario_delivery_no_change() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        scenarios={"mockery": {}},
        transport_types=ALL_TRANSPORT_TYPES,
        services=MOCK_SERVICES,
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("email", "mobile_push", "chime")


async def test_scenario_delivery_disable() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        scenarios={"mockery": {"delivery": {"chime": {"enabled": False}}}},
        services=MOCK_SERVICES,
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("email", "mobile_push")


async def test_scenario_delivery_enable() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        scenarios={"mockery": {"delivery": {"chime": {"enabled": True}}}},
        transport_types=ALL_TRANSPORT_TYPES,
        services=MOCK_SERVICES,
    )
    await ctx.test_initialize()
    ctx.delivery_registry.deliveries["chime"].enabled = False

    uut = Notification(ctx, "testing 123", action_data={ATTR_SCENARIOS_APPLY: "mockery"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("email", "mobile_push", "chime")


async def test_explicit_list_of_deliveries() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: "mobile_push"})
    await uut.initialize()
    assert list(uut.selected_deliveries) == ["mobile_push"]


async def test_action_data_disable_delivery() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        scenarios={"mockery": {}},
        transport_types=ALL_TRANSPORT_TYPES,
        services=MOCK_SERVICES,
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx, "testing 123", action_data={"delivery": {"mobile_push": {"enabled": False}}, ATTR_SCENARIOS_APPLY: "mockery"}
    )
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("email", "chime")


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
        deliveries={"chatty": {CONF_TRANSPORT: "email", CONF_ACTION: "notify.smtp", CONF_INCLUSION: ["explicit"]}},
        services={"notify": ["smtp", "mobile_app_kidphone", "mobile_app_joephone"]},
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123")
    await uut.initialize()
    await uut.deliver()
    assert first_envelope(uut, "mobile_push").target.mobile_app_ids == ["mobile_app_joephone", "mobile_app_kidphone"]
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
        Envelope(
            Delivery("mail", ctx.delivery_config("mail"), email),
            uut,
            target=Target({"email": ["bob@test.com", "jane@test.com"], "person_id": ["person.bob", "person.jane"]}),
        )
    ]


async def test_build_targets_for_simple_case() -> None:
    ctx = TestingContext()
    await ctx.test_initialize()
    generic = ctx.transport(TRANSPORT_GENERIC, force=True)
    delivery = Delivery("simple", {}, generic)

    uut = Notification(ctx, "testing 123")
    recipients: list[Target] = uut.generate_targets(delivery)
    bundles = uut.generate_envelopes(delivery, recipients)
    assert bundles == [Envelope(Delivery("simple", {}, generic), uut)]


async def test_dict_of_delivery_tuning_does_not_restrict_deliveries() -> None:
    ctx = TestingContext(
        deliveries=DELIVERIES,
        transports=TRANSPORTS,
        transport_types=ALL_TRANSPORT_TYPES,
        services=MOCK_SERVICES,
    )
    await ctx.test_initialize()

    uut = Notification(ctx, "testing 123", action_data={CONF_DELIVERY: {"mobile_push": {}}})
    await uut.initialize()
    assert list(uut.selected_deliveries) == unordered("email", "mobile_push", "chime")


async def test_snapshot_url() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
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
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
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
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
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
    ctx = TestingContext(
        deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES, services=MOCK_SERVICES
    )
    await ctx.test_initialize()
    uut = Notification(
        ctx,
        "testing 123",
        action_data={
            CONF_DELIVERY: ["mobile_push"],
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
        services=MOCK_SERVICES,
        deliveries={
            "fallback": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.LAST,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            },
            "eager": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light1"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.FIRST,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            },
            "whatever": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light2"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.ANY,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            },
            "or_whatever": {
                CONF_ACTION: "custom.tweak",
                CONF_TARGET: ["custom.light3"],
                CONF_TRANSPORT: "generic",
                CONF_SELECTION_RANK: SelectionRank.ANY,
                CONF_INCLUSION: [INCLUSION_DEFAULT],
            },
            "implicitly_last": {CONF_TARGET: ["notify.me"], CONF_TRANSPORT: "notify_entity"},
        },
    )
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123")
    await uut.initialize()

    assert len(list(uut.selected_deliveries)) == 8
    assert next(iter(uut.selected_deliveries)) == "eager"
    assert list(uut.selected_deliveries)[1:5] == unordered("mobile_push", "whatever", "email", "or_whatever")
    assert list(uut.selected_deliveries)[-3:] == unordered("notify_entity", "fallback", "implicitly_last")
    assert list(uut.selected_deliveries)[-1] == "notify_entity"  # LAST and auto-generated


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


async def test_envelope_person_ids_are_only_recipients_the_envelope_reaches() -> None:
    """Selecting targets for a delivery keeps person_ids, but each envelope's target only ends up
    with those whose own targets for that delivery are actually in it - not a recipient with
    nothing this delivery can send to (bob has no phone number)."""
    ctx = TestingContext(
        deliveries={"sms": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}},
        services={"notify": ["smsify"]},
        recipients=[
            {CONF_PERSON: "person.alice", CONF_PHONE_NUMBER: "+339875000123"},
            {CONF_PERSON: "person.bob"},
            {CONF_PERSON: "person.carol", CONF_PHONE_NUMBER: "+339875000456"},
        ],
        viable_transport_types=[SMSTransport],
    )
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", target=["person.alice", "person.bob", "person.carol"])
    await uut.initialize()

    targets = uut.generate_targets(ctx.delivery("sms"))

    assert len(targets) == 1
    assert targets[0].phone == ["+339875000123", "+339875000456"]
    assert targets[0].person_ids == ["person.alice", "person.carol"]


async def test_envelope_person_ids_exclude_recipient_whose_address_went_in_earlier_envelope() -> None:
    """With unique_targets, an address already sent to by an earlier delivery is dropped, and so
    is the recipient it belonged to - they were reached by that earlier envelope instead."""
    ctx = TestingContext(
        deliveries={
            "sms": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"},
            "sms2": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"},
        },
        services={"notify": ["smsify"]},
        recipients=[{CONF_PERSON: "person.alice", CONF_PHONE_NUMBER: "+339875000123"}],
        viable_transport_types=[SMSTransport],
    )
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", target=["person.alice"])
    await uut.initialize()

    first = uut.generate_targets(ctx.delivery("sms"))
    second = uut.generate_targets(ctx.delivery("sms2"))

    assert first[0].person_ids == ["person.alice"]
    assert second[0].phone == []
    assert second[0].person_ids == []


async def test_recipient_with_no_resolvable_target_does_not_block_delivery_target_fallback() -> None:
    """person_ids surviving target selection must not count as having found a target - a delivery
    that only falls back to its own configured target when nothing else resolves still has to."""
    ctx = TestingContext(
        deliveries={
            "sms": {
                CONF_TRANSPORT: TRANSPORT_SMS,
                CONF_ACTION: "notify.smsify",
                CONF_TARGET: ["+447700900123"],
                CONF_TARGET_USAGE: "no_delivery",
            }
        },
        services={"notify": ["smsify"]},
        recipients=[{CONF_PERSON: "person.bob"}],
        viable_transport_types=[SMSTransport],
    )
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", target=["person.bob"])
    await uut.initialize()

    targets = uut.generate_targets(ctx.delivery("sms"))

    assert len(targets) == 1
    assert targets[0].phone == ["+447700900123"]
    assert targets[0].person_ids == []


@fixture
async def personal_delivery_context() -> TestingContext:
    ctx = TestingContext(
        deliveries={"sms": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"}},
        services={"notify": ["smsify"]},
        recipients=[
            {CONF_PERSON: "person.alice", CONF_PHONE_NUMBER: "+339875000123"},
            {CONF_PERSON: "person.bob"},
            {CONF_PERSON: "person.carol", CONF_PHONE_NUMBER: "+339875000456"},
        ],
        viable_transport_types=[SMSTransport],
    )
    await ctx.test_initialize()
    for p in ctx._recipients:
        ctx.people_registry.people[p[CONF_PERSON]].notify_entity = Mock(spec=RecipientNotifyEntity)
    return ctx


async def test_record_result_notifies_recipient_notify_entity_on_delivery(personal_delivery_context: TestingContext) -> None:
    """A successful envelope delivery updates the involved recipient's notify.recipient_<name>
    entity (record_notification()), regardless of what target form got it there - a plain
    person_id, an email/phone/mobile override, or notify.recipient_<name> itself (converted to
    person_id by convert_notify_entities() before delivery). Every Recipient's Target always
    includes its own person_id (Recipient.initialize()), so that's the reliable link back from
    an arbitrary envelope to the Recipient objects it reached."""

    uut = Notification(personal_delivery_context, "testing 123", target=["person.alice"])
    await uut.initialize()
    await uut.deliver()

    personal_delivery_context.people_registry.people["person.alice"].notify_entity.record_notification.assert_called_once()  # type: ignore[attr-defined,union-attr]  #ty: ignore[unresolved-attribute]
    personal_delivery_context.people_registry.people["person.bob"].notify_entity.record_notification.assert_not_called()  # type: ignore[attr-defined,union-attr]  #ty: ignore[unresolved-attribute]
    personal_delivery_context.people_registry.people["person.carol"].notify_entity.record_notification.assert_not_called()  # type: ignore[attr-defined,union-attr]  #ty: ignore[unresolved-attribute]


async def test_record_result_notifies_recipient_notify_entity_once_however_many_deliveries_reach_them() -> None:
    """Each update is a state write on the entity, so a recipient reached by several deliveries
    (here, both SMS and email) is only recorded once for the notification - otherwise the logbook
    fills with identical entries, all at the same moment and under the same context"""
    ctx = TestingContext(
        deliveries={
            "sms": {CONF_TRANSPORT: TRANSPORT_SMS, CONF_ACTION: "notify.smsify"},
            "mail": {CONF_TRANSPORT: "email", CONF_ACTION: "notify.smtp"},
        },
        services={"notify": ["smsify", "smtp"]},
        recipients=[{CONF_PERSON: "person.alice", CONF_PHONE_NUMBER: "+339875000123", CONF_EMAIL: "alice@test.com"}],
        viable_transport_types=[SMSTransport, EmailTransport],
    )
    await ctx.test_initialize()
    notify_entity = Mock(spec=RecipientNotifyEntity)
    ctx.people_registry.people["person.alice"].notify_entity = notify_entity

    uut = Notification(ctx, "testing 123", target=["person.alice"])
    await uut.initialize()
    await uut.deliver()

    assert len(uut.delivered_envelopes) == 2
    notify_entity.record_notification.assert_called_once()


async def test_record_result_passes_calling_context_to_recipient_notify_entity(
    personal_delivery_context: TestingContext,
) -> None:
    """The context of the supernotify.notify call that caused the delivery is handed on, so the
    recipient's notify entity state change can be attributed to it"""
    calling_context = HAContext(user_id="user123")

    uut = Notification(personal_delivery_context, "testing 123", target=["person.alice"], ha_context=calling_context)
    await uut.initialize()
    await uut.deliver()

    personal_delivery_context.people_registry.people["person.alice"].notify_entity.record_notification.assert_called_once_with(  # type: ignore[attr-defined,union-attr]  #ty: ignore[unresolved-attribute]
        calling_context
    )


async def test_record_result_skips_recipients_without_a_notify_entity(personal_delivery_context: TestingContext) -> None:
    """A recipient with no notify_entity set (e.g. the notify platform hasn't loaded yet, or
    tests building SupernotifyAction directly without a config entry) is silently skipped -
    same tolerant fallback pattern used elsewhere for entity-less operation."""

    personal_delivery_context.people_registry.people["person.alice"].notify_entity = None
    personal_delivery_context.people_registry.people["person.bob"].notify_entity = None
    personal_delivery_context.people_registry.people["person.carol"].notify_entity = None

    uut = Notification(personal_delivery_context, "testing 123")
    await uut.initialize()
    await uut.deliver()


async def test_notification_accepts_dict_shaped_target_without_crashing() -> None:
    ctx = TestingContext(recipients=[{CONF_PERSON: "person.alice"}])
    await ctx.test_initialize()

    uut = Notification(ctx, "a wee test", target={"entity_id": ["person.alice"]})

    assert uut._target is not None
    assert uut._target.person_ids == ["person.alice"]


async def test_contents_omits_unpopulated_exposed_fields() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123")
    await uut.initialize()

    contents = uut.contents()

    for key in ("message_html", "spoken_message", "extra_data", "actions"):
        assert key not in contents


async def test_contents_places_populated_exposed_fields_by_preferred_order() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
    await ctx.test_initialize()
    uut = Notification(
        ctx, "testing 123", action_data={"spoken_message": "say this", "message_html": "<b>hi</b>", "colour": "red"}
    )
    await uut.initialize()

    keys = list(uut.contents())

    assert keys[keys.index("message") : keys.index("message") + 4] == ["message", "spoken_message", "message_html", "priority"]
    assert "extra_data" in keys  # populated but not in preferred_order, so still exposed, after the ordered fields
    assert keys.index("extra_data") > keys.index("priority")


async def test_delivery_provenance_records_each_source() -> None:
    """The trace says which scenario, recipient, default inclusion or the call itself switched each
    delivery on or off - the per-stage delivery_selection lists only have the combined result"""
    ctx = TestingContext(
        recipients=[{CONF_PERSON: "person.joe", CONF_EMAIL: "joe@mctest.org", CONF_DELIVERY: {"chatty": {CONF_ENABLED: True}}}],
        deliveries={
            "chime": {CONF_TRANSPORT: "chime", CONF_INCLUSION: ["default"]},
            "chatty": {CONF_TRANSPORT: "email", CONF_ACTION: "notify.smtp", CONF_INCLUSION: ["explicit"]},
        },
        transports=TRANSPORTS,
        scenarios={
            "night": {"delivery": {"chime": {"enabled": False}, "mobile_push": {"enabled": True}}},
            "loud": {"delivery": {"chime": {"enabled": True}}},
        },
        transport_types=ALL_TRANSPORT_TYPES,
        services={"notify": [*MOCK_SERVICES["notify"], {"action": "smtp"}]},  # type: ignore[list-item] # ty: ignore[invalid-argument-type]
    )
    await ctx.test_initialize()

    uut = Notification(
        ctx,
        "testing 123",
        action_data={ATTR_SCENARIOS_APPLY: ["night", "loud"], "delivery": {"email": {"enabled": False}}, "debug": True},
    )
    await uut.initialize()

    archived = uut.contents()  # a recipient's personal delivery used to break this, DeliveryTargetOverride.as_dict
    assert archived["selected_deliveries"]["chatty"] == {"fixed": ["person.joe"], "include": [], "exclude": []}
    provenance = archived["delivery_provenance"]
    assert provenance["chime"] == {"enabled_by": ["scenario:loud", "default"], "disabled_by": ["scenario:night"]}
    assert provenance["mobile_push"] == {"enabled_by": ["scenario:night", "default"]}
    assert provenance["email"] == {"enabled_by": ["default"], "disabled_by": ["call"]}
    assert provenance["chatty"] == {"enabled_by": ["recipient:joe"]}
    # the combined lists are unchanged
    assert "chime" in uut.debug_trace.delivery_selection["scenario_disable_deliveries"]
    assert "chime" not in uut.selected_deliveries
    assert "email" not in uut.selected_deliveries


async def test_delivery_provenance_recorded_without_debug() -> None:
    ctx = TestingContext(deliveries=DELIVERIES, transports=TRANSPORTS, transport_types=ALL_TRANSPORT_TYPES)
    await ctx.test_initialize()
    uut = Notification(ctx, "testing 123", action_data={"delivery": {"email": {"enabled": False}}})
    await uut.initialize()
    # minimal archive content, as for a notification without debug and outside the diagnostics outcomes
    minimal = uut.contents(diagnostics=False)
    assert minimal["delivery_provenance"]["email"]["disabled_by"] == ["call"]
    assert "debug_trace" not in minimal
