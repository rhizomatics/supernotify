from homeassistant.exceptions import HomeAssistantError

from custom_components.supernotify.model import DebugTrace, Target, TargetRequired

from .hass_setup_lib import assert_json_round_trip


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
    assert uut == uut
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


def test_target_required() -> None:
    assert TargetRequired("always") == TargetRequired.ALWAYS
    assert TargetRequired("never") == TargetRequired.NEVER
    assert TargetRequired("optional") == TargetRequired.OPTIONAL
    assert TargetRequired("true") == TargetRequired.ALWAYS
    assert TargetRequired("false") == TargetRequired.OPTIONAL


def test_debug_trace() -> None:
    uut = DebugTrace("test message", "test title", {}, ["joe@mctest.org", "siren.hallway"])
    uut.record_target("mixed", "sortout", [Target("mrst@mctest.org"), Target("switch.gong")])
    uut.record_delivery_artefact("plain_email", "foo", {"a": 12, "header": False})
    uut.record_delivery_selection("pre-cogitate", ["plain_email", "siren"])
    uut.record_delivery_exception("plain_email", "validating", HomeAssistantError())
    result = uut.contents()
    assert "foo" in result["delivery_artefacts"]["plain_email"]

    assert_json_round_trip(uut.contents())
