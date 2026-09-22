from homeassistant.exceptions import HomeAssistantError

from custom_components.supernotify.model import DataFilter, DebugTrace, SelectionRule, Target, TargetRequired

from .hass_setup_lib import assert_json_round_trip


def test_target_required() -> None:
    assert TargetRequired("always") == TargetRequired.ALWAYS
    assert TargetRequired("never") == TargetRequired.NEVER
    assert TargetRequired("optional") == TargetRequired.OPTIONAL
    assert TargetRequired("true") == TargetRequired.ALWAYS
    assert TargetRequired("false") == TargetRequired.OPTIONAL


def test_selection_rule_construction():
    uut = SelectionRule(None)
    assert uut.include is None
    assert uut.exclude is None

    uut = SelectionRule("Goog.*")
    assert uut.include == ["Goog.*"]
    assert uut.exclude is None

    uut = SelectionRule(["Goog.*", "Nest.*"])
    assert uut.include == ["Goog.*", "Nest.*"]
    assert uut.exclude is None

    uut = SelectionRule({"include": ["Goog.*", "Nest.*"], "exclude": ["Amazon.*"]})
    assert uut.include == ["Goog.*", "Nest.*"]
    assert uut.exclude == ["Amazon.*"]


def test_selection_rule_match():
    uut = SelectionRule({"include": ["Goog.*", "Nest.*"], "exclude": [".*Legacy"]})
    assert uut.match("Google Pixie")
    assert uut.match("Nest 99")
    assert not uut.match("Google Pixie Legacy")
    assert not uut.match(None)
    assert not uut.match("Random Device")

    uut = SelectionRule({"include": ["Goog.*", "Nest.*"]})
    assert uut.match("Google Pixie")
    assert uut.match("Nest 99")
    assert uut.match("Google Pixie Legacy")
    assert not uut.match(None)
    assert not uut.match("Random Device")
    assert uut.match(["Foo", "Bar", "Nest Pro"])
    assert not uut.match(["Foo", "Bar"])

    uut = SelectionRule({"exclude": [".*Legacy"]})
    assert uut.match("Google Pixie")
    assert uut.match("Nest 99")
    assert not uut.match("Google Pixie Legacy")
    assert uut.match(None)
    assert uut.match("Random Device")
    assert uut.match(v=["Foo", "Bar"])
    assert not uut.match(v=["Foo", "Bar", "The Legacy"])

    uut = SelectionRule(None)
    assert uut.match("Google Pixie")
    assert uut.match("Anything")


def test_datafilter_applies_flat_match():
    uut = DataFilter(["good", "bad"])
    assert uut.apply({"good": 123}) == {"good": 123}
    assert uut.apply({"good": 123, "foo": 129}) == {"good": 123}
    assert uut.apply({}) == {}
    assert uut.apply({"data": {"priority": 3}, "bad": True}) == {"bad": True}


def test_datafilter_applies_prune_empty():
    uut = DataFilter({})
    assert uut.apply({"data": {}}, prune_empty=True) == {}
    assert uut.apply({"data": {}}, prune_empty=False) == {"data": {}}


def test_datafilter_applies_nested_match():
    uut = DataFilter({"exclude": {"foo": None, "data": {"media": {"camera": None}}}})
    assert uut.apply({"good": 123}) == {"good": 123}
    assert uut.apply({"good": 123, "foo": 129}) == {"good": 123}
    assert uut.apply({}) == {}
    assert uut.apply({"data": {"priority": 3, "media": {"camera": {"entity_id": "barncam"}, "snap": True}}}) == {
        "data": {"priority": 3, "media": {"snap": True}}
    }


def test_debug_trace() -> None:
    uut = DebugTrace("test message", "test title", {}, ["joe@mctest.org", "siren.hallway"])
    uut.record_target("mixed", "sortout", [Target("mrst@mctest.org"), Target("switch.gong")])
    uut.record_delivery_artefact("plain_email", "foo", {"a": 12, "header": False})
    uut.record_delivery_selection("pre-cogitate", ["plain_email", "siren"])
    uut.record_delivery_exception("plain_email", "validating", HomeAssistantError())
    result = uut.contents()
    assert "foo" in result["delivery_artefacts"]["plain_email"]

    assert_json_round_trip(uut.contents())


def test_debug_trace_for_targets():
    uut = DebugTrace("message", "title", {}, {})
    uut.record_target("omni", "stage_1", Target(["switch.hall", "joe@mctoe.com"]))
    uut.record_target("omni", "stage_2", Target(["switch.hall", "joe@mctoe.com"]))
    uut.record_target("omni", "stage_3", Target(["switch.hall", "joe@mctoe.com"]))
    uut.record_target("omni", "stage_4", Target(["joe@mctoe.com"]))
    uut.record_target("omni", "stage_5", Target(["joe@mctoe.com", "home@24acacia.ave"]))
    uut.record_target("omni", "stage_6", Target())

    assert len(uut.contents()["resolved"]["omni"]) == 6
    assert uut.contents()["resolved"]["omni"]["stage_1"] == {"email": ["joe@mctoe.com"], "entity_id": ["switch.hall"]}
    assert uut.contents()["resolved"]["omni"]["stage_2"] == "NO_CHANGE"
    assert uut.contents()["resolved"]["omni"]["stage_3"] == "NO_CHANGE"
    assert uut.contents()["resolved"]["omni"]["stage_4"] == {"email": ["joe@mctoe.com"]}
    assert uut.contents()["resolved"]["omni"]["stage_5"] == {"email": ["joe@mctoe.com", "home@24acacia.ave"]}
    assert uut.contents()["resolved"]["omni"]["stage_6"] == {}
