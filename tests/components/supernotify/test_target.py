from unittest.mock import Mock

from custom_components.supernotify.model import SelectionRule
from custom_components.supernotify.target import Target, TargetEntityCategory


def test_target_in_dict_mode() -> None:
    uut: Target = Target({
        "email": ["joe.mctoe@kmail.com"],
        "entity_id": ["media_player.kitchen", "notify.garden"],
        "phone": "+43985951039393",
        "person_id": "person.joe_mctoe",
        "device_id": ["000044449999aaaa00003333ffff7777"],
        "telegram": "@myhome",
        "slack": ["big_kid"],
        "area_id": "backyard",
        "label_id": [],
        "floor_id": ["01", "02"],
        "klaxon": ["dive_dive_dive"],
    })

    assert uut.entity_ids == ["media_player.kitchen", "notify.garden"]
    assert uut.person_ids == ["person.joe_mctoe"]
    assert uut.phone == ["+43985951039393"]
    assert uut.device_ids == ["000044449999aaaa00003333ffff7777"]
    assert uut.email == ["joe.mctoe@kmail.com"]
    assert uut.custom_ids("klaxon") == ["dive_dive_dive"]
    assert uut.custom_ids("telegram") == ["@myhome"]
    assert uut.custom_ids("slack") == ["big_kid"]
    assert uut.label_ids == []
    assert uut.floor_ids == ["01", "02"]
    assert uut.area_ids == ["backyard"]


def test_target_in_list_mode() -> None:
    uut = Target([
        "joe.mctoe@kmail.com",
        "media_player.kitchen",
        "+43985951039393",
        "person.joe_mctoe",
        "notify.garden",
        "000044449999aaaa00003333ffff7777",
        "@mctoe",
    ])
    assert uut.entity_ids == ["media_player.kitchen", "notify.garden"]
    assert uut.person_ids == ["person.joe_mctoe"]
    assert uut.phone == ["+43985951039393"]
    assert uut.device_ids == ["000044449999aaaa00003333ffff7777"]
    assert uut.email == ["joe.mctoe@kmail.com"]
    assert uut.custom_ids("_UNKNOWN_") == ["@mctoe"]
    assert uut.label_ids == []
    assert uut.floor_ids == []
    assert uut.area_ids == []
    assert uut.has_unknown_targets()


def test_target_in_scalar_mode() -> None:
    assert Target("media_player.kitchen").entity_ids == ["media_player.kitchen"]
    assert Target("000044449999aaaa00003333ffff7777").device_ids == ["000044449999aaaa00003333ffff7777"]
    assert Target("person.joe_mctoe").person_ids == ["person.joe_mctoe"]
    assert Target([]).entity_ids == []


def test_simple_entity() -> None:
    uut = Target("light.hallway")
    assert uut.entity_ids == ["light.hallway"]
    assert uut.device_ids == []
    assert not uut.has_unknown_targets()


def test_category_access() -> None:
    uut = Target([
        "joe.mctoe@kmail.com",
        "media_player.kitchen",
        "+43985951039393",
        "person.joe_mctoe",
        "notify.garden",
        "000044449999aaaa00003333ffff7777",
        "@mctoe",
    ])
    assert uut.for_category("entity_id") == ["media_player.kitchen", "notify.garden"]
    uut.extend("label_id", "tag1")
    uut.extend("label_id", ["tag1", "tag2"])
    assert uut.for_category("label_id") == ["tag1", "tag2"]
    uut.extend("_UNKNOWN_", "@mctoe2")
    assert uut.for_category("_UNKNOWN_") == ["@mctoe", "@mctoe2"]
    assert uut.custom_ids("_UNKNOWN_") == ["@mctoe", "@mctoe2"]


def test_target_correctly_selects_valid_emails() -> None:
    good = [
        "test421@example.com",
        "t@example.com",
        "t.1.g@example.com",
        "test-hyphen+ext@example.com",
        "test@sub.topsub.example.com",
        "test+fancy_rules@example.com",
    ]
    bad = ["test@example@com", "sub.topsub.example.com", "test+fancy_rules@com", "", "@", "a@b"]
    assert Target(good + bad).email == good
    assert Target({"email": good + bad}).email == good
    assert Target({"email": good + bad}).for_category("email") == good


def test_target_sorts_out_big_flat_list() -> None:
    uut = Target([
        "me@mctest.org",
        "switch.lounge",
        "person.joe_mctest",
        "00001111222233334444555566667777",
        "@joey",
        "00001111122223333444455556666",
        "+4350404183736",
    ])
    assert uut.email == ["me@mctest.org"]
    assert uut.entity_ids == ["switch.lounge"]
    assert uut.person_ids == ["person.joe_mctest"]
    assert uut.for_category("entity_id") == ["switch.lounge"]
    assert uut.device_ids == ["00001111222233334444555566667777"]
    assert uut.phone == ["+4350404183736"]
    assert uut.custom_ids("_UNKNOWN_") == ["@joey", "00001111122223333444455556666"]


def test_target_category_prefix_in_list_mode() -> None:
    # a prefix is always a target *category* (topic, discord_channel, ...), never a
    # transport or delivery name directly - those are only addressable via the mapping form
    uut = Target([
        "me@house.org",
        "+48323232211",
        "discord_channel:9585",
        "topic:my/topic/name",
    ])
    assert uut.email == ["me@house.org"]
    assert uut.phone == ["+48323232211"]
    assert uut.custom_ids("discord_channel") == ["9585"]
    assert uut.custom_ids("topic") == ["my/topic/name"]
    assert not uut.has_unknown_targets()


def test_target_category_prefix_in_scalar_mode() -> None:
    assert Target("topic:my/topic/name").custom_ids("topic") == ["my/topic/name"]


def test_target_category_prefix_only_recognised_in_list_form() -> None:
    # the mapping form is taken verbatim - no colon-splitting - so values that clash with the
    # prefix syntax (e.g. already containing a colon) can still be expressed unambiguously
    uut = Target({"topic": "topic:my/topic/name"})
    assert uut.custom_ids("topic") == ["topic:my/topic/name"]


def test_target_category_prefix_requires_known_category() -> None:
    # an unrecognised prefix isn't split - falls through to the flat unknown-custom bucket.
    # This includes transport/delivery names - "mqtt" is a transport, not a category, so
    # doesn't qualify a prefix (use the mapping form, `target: {mqtt: value}`, for that).
    uut = Target(["notavalidcategory:foo", "mqtt:my/topic/name"])
    assert uut.custom_ids("notavalidcategory") == []
    assert uut.custom_ids("mqtt") == []
    assert uut.custom_ids("_UNKNOWN_") == ["notavalidcategory:foo", "mqtt:my/topic/name"]


def test_has_resolved() -> None:
    assert not Target({"label_id": "tag001"}).has_resolved_target()
    assert not Target({"person_id": "person.cuth_bert"}).has_resolved_target()
    assert Target({"telegram": "@bob"}).has_resolved_target()
    assert Target("switch.alarm_bell").has_resolved_target()


def test_direct() -> None:
    uut: Target = Target(
        {"label_id": "tag001", "person_id": ["person.cuth_bert"], "telegram": "@bob", "entity_id": ["switch.alarm_bell"]},
        target_data={"foo": 123, "bar": True},
    )
    assert uut.direct() == Target(
        {"telegram": "@bob", "entity_id": ["switch.alarm_bell"]}, target_data={"foo": 123, "bar": True}
    )


def test_equality() -> None:
    uut = Target(
        ["me@mctest.org", "switch.lounge", "person.joe_mctest", "+4350404183736"], target_data={"foo": 123, "bar": True}
    )
    assert uut == uut  # noqa: PLR0124
    assert uut != Target()
    assert uut != Target(["me@mctest.org", "switch.lounge", "person.joe_mctest", "+4350404183736"])
    assert uut != Target(
        ["me@mctest.org", "switch.lounge", "person.joe_mctest", "+4350404183736"], target_data={"foo": 123, "bar": False}
    )


def test_addition() -> None:
    uut = Target(
        ["me@mctest.org", "switch.lounge", "person.joe_mctest", "+4350404183736"], target_data={"foo": 123, "bar": True}
    )
    new = uut + Target(["light.hall"])
    assert new.entity_ids == ["switch.lounge", "light.hall"]
    assert new.target_data == {"foo": 123, "bar": True}


def test_minus() -> None:
    target1: Target = Target({
        "label_id": "tag001",
        "person_id": ["person.cuth_bert"],
        "telegram": "@bob",
        "redsky": "bobby3",
        "email": ["me@mctest.org"],
        "entity_id": ["switch.alarm_bell", "siren.downstairs"],
    })
    target2: Target = target1 - (
        Target({
            "label_id": "tag001",
            "person_id": ["person.cuth_bert"],
            "telegram": "@bob",
            "email": ["you@mctest.org"],
            "x": "@bob885845",
            "entity_id": ["siren.downstairs", "siren.upstairs"],
        })
    )

    assert target2 == Target({"email": ["me@mctest.org"], "entity_id": ["switch.alarm_bell"]})


def test_split_by_target_data():
    uut = Target(
        ["me@mctest.org", "switch.lounge", "person.joe_mctest", "+4350404183736"], target_data={"foo": 123, "bar": True}
    )
    uut += Target(
        ["switch.kitchen", "person.bey_eksin", "switch.lounge"], target_data={"fi": 123, "fum": True}, target_specific_data=True
    )
    uut += Target(["notify.foo", "notify.api"], target_data={"fi": 912, "widget": False}, target_specific_data=True)
    splits = uut.split_by_target_data()
    assert splits == [
        Target(["switch.kitchen", "person.bey_eksin", "switch.lounge"], target_data={"fi": 123, "fum": True}),
        Target(["notify.foo", "notify.api"], target_data={"fi": 912, "widget": False}),
        Target(["me@mctest.org", "person.joe_mctest", "+4350404183736"], target_data={"foo": 123, "bar": True}),
    ]


def test_select_keeps_person_ids_whatever_the_delivery_declares() -> None:
    """person_ids aren't delivered to, but are how an envelope is linked back to the
    recipients it reaches, so selection must not strip them like other undeclared categories"""
    uut = Target(["person.alice", "+4350404183736", "me@mctest.org"])

    selected = uut.select(["phone"], ("sms", "sms"), Mock())

    assert selected.phone == ["+4350404183736"]
    assert selected.email == []
    assert selected.person_ids == ["person.alice"]


def test_select_does_not_apply_target_selector_to_person_ids() -> None:
    uut = Target(["person.alice", "+4350404183736", "+4477009001234"])

    selected = uut.select(["phone"], ("sms", "sms"), Mock(), SelectionRule({"include": [r"\+4350.*"]}))

    assert selected.phone == ["+4350404183736"]
    assert selected.person_ids == ["person.alice"]


def test_select_only_looks_up_entity_platform_when_a_platform_is_declared() -> None:
    hass_api = Mock()
    hass_api.platform_for_entity.side_effect = lambda entity_id: {"notify.echo": "alexa_devices"}.get(entity_id)
    uut = Target(["notify.echo", "notify.other", "switch.lamp"])

    by_domain = uut.select([TargetEntityCategory(domain="notify")], ("n", "n"), hass_api)
    assert by_domain.entity_ids == ["notify.echo", "notify.other"]
    hass_api.platform_for_entity.assert_not_called()

    by_platform = uut.select([TargetEntityCategory(domain="notify", platform="alexa_devices")], ("n", "n"), hass_api)
    assert by_platform.entity_ids == ["notify.echo"]
    # switch.lamp is rejected on domain alone, without needing its platform
    assert hass_api.platform_for_entity.call_count == 2


def test_select_leaves_original_target_untouched() -> None:
    uut = Target(["person.alice", "+4350404183736", "me@mctest.org"])

    uut.select(["phone"], ("sms", "sms"), Mock())

    assert uut.email == ["me@mctest.org"]


def test_select_drops_target_specific_data_for_values_it_filters_out() -> None:
    """Otherwise split_by_target_data(), which rebuilds targets from the target-specific data,
    would bring a filtered-out value back into a delivery that can't handle it"""
    uut = Target(["switch.kitchen", "me@mctest.org"], target_data={"fi": 123}, target_specific_data=True)

    selected = uut.select(["email"], ("mail", "mail"), Mock())

    assert selected.target_specific_data == {("email", "me@mctest.org"): {"fi": 123}}
    assert selected.split_by_target_data() == [Target(["me@mctest.org"], target_data={"fi": 123})]


def test_split_by_target_data_drops_leftover_that_is_only_person_ids() -> None:
    """person_ids survive target selection, but aren't deliverable - once the target-specific data
    has been split out, a remainder of nothing but person_ids isn't a target of its own"""
    uut = Target(["person.joe_mctest"])
    uut += Target(["switch.kitchen"], target_data={"fi": 123}, target_specific_data=True)

    assert uut.split_by_target_data() == [Target(["switch.kitchen"], target_data={"fi": 123})]
