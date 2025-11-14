from custom_components.supernotify.model import Target


def test_target_in_dict_mode() -> None:
    uut = Target({
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


def test_target_in_scalar_mode() -> None:
    assert Target("media_player.kitchen").entity_ids == ["media_player.kitchen"]
    assert Target("000044449999aaaa00003333ffff7777").device_ids == ["000044449999aaaa00003333ffff7777"]
    assert Target("person.joe_mctoe").person_ids == ["person.joe_mctoe"]
    assert Target([]).entity_ids == []


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
    uut = Target(
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
    target1 = Target({
        "label_id": "tag001",
        "person_id": ["person.cuth_bert"],
        "telegram": "@bob",
        "redsky": "bobby3",
        "email": ["me@mctest.org"],
        "entity_id": ["switch.alarm_bell", "siren.downstairs"],
    })
    target2 = target1 - (
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
