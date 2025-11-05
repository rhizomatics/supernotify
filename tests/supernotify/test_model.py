from custom_components.supernotify.model import Target


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
    assert uut.device_ids == ["00001111222233334444555566667777"]
    assert uut.phone == ["+4350404183736"]
    assert uut.other_ids == ["@joey", "00001111122223333444455556666"]


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
