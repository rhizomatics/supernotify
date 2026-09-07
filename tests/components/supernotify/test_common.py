import datetime as dt
from unittest.mock import Mock

from custom_components.supernotify.common import (
    CallRecord,
    DupeChecker,
    boolify,
    ensure_dict,
    ensure_list,
    int_or_none,
    safe_extend,
    safe_get,
)
from custom_components.supernotify.const import ATTR_DUPE_POLICY_MT, ATTR_DUPE_POLICY_NONE, CONF_DUPE_POLICY
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification


def test_int_or_none():
    assert int_or_none("cheese!") is None
    assert int_or_none(23) == 23
    assert int_or_none("23") == 23
    assert int_or_none(23.12) == 23
    assert int_or_none("-23") == -23
    assert int_or_none("") is None


def test_safe_get():
    assert safe_get(None, "foo") is None
    assert safe_get({}, "foo") is None
    assert safe_get({"foo": "fum"}, "foo") == "fum"


def test_safe_extend():
    assert safe_extend(None, None) == []  # type:ignore[invalid-argument-type]  # ty: ignore[invalid-argument-type]
    assert safe_extend(1, 3) == [1, 3]  # type:ignore[invalid-argument-type]  # ty: ignore[invalid-argument-type]
    assert safe_extend([], 3) == [3]
    assert safe_extend([1], (2, 3)) == [1, 2, 3]
    assert safe_extend([1, 2], 3) == [1, 2, 3]


def test_ensure_list():
    assert ensure_list((1, 2, 3)) == [1, 2, 3]
    assert ensure_list([1, 2, 3]) == [1, 2, 3]
    assert ensure_list([]) == []
    assert ensure_list(3) == [3]
    assert ensure_list("foo") == ["foo"]


def test_ensure_dict():
    assert ensure_dict({}) == {}
    assert ensure_dict(None) == {}
    assert ensure_dict(["a", 123]) == {"a": None, 123: None}
    assert ensure_dict(["a", 123], default=False) == {"a": False, 123: False}
    assert ensure_dict({"a": 123}) == {"a": 123}
    assert ensure_dict("a", default=123) == {"a": 123}


def test_call_record():
    assert CallRecord(
        dt.datetime(2026, 3, 12, 8, 14, 3, 100, tzinfo=dt.UTC), 13.4, "switch", "toggle", {}, None, None
    ).contents() == {
        "timestamp": "2026-03-12T08:14:03.000100+00:00",
        "domain": "switch",
        "action": "toggle",
        "action_data": {},
        "elapsed": 13.4,
        "debug": False,
    }


def test_dupe_check_suppresses_same_priority_and_message() -> None:
    delivery = Mock(name="tester")
    uut = DupeChecker({})
    e1 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e1) is False
    e2 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e2) is True


def test_dupe_check_allows_higher_priority_and_same_message() -> None:
    delivery = Mock(name="tester")
    uut = DupeChecker({})
    e1 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e1) is False
    e2 = Envelope(delivery, Notification(Mock(), "message here", "title here"), data={"priority": "high"})
    assert uut.check(e2) is False


def test_dupe_policy_mt_suppresses_same_message() -> None:
    delivery = Mock(name="tester")
    uut = DupeChecker({CONF_DUPE_POLICY: ATTR_DUPE_POLICY_MT})
    e1 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e1) is False
    e2 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e2) is True


def test_dupe_policy_mt_suppresses_higher_priority_same_message() -> None:
    """Unlike MTSLP, MT suppresses even when priority escalates."""
    delivery = Mock(name="tester")
    uut = DupeChecker({CONF_DUPE_POLICY: ATTR_DUPE_POLICY_MT})
    e1 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e1) is False
    e2 = Envelope(delivery, Notification(Mock(), "message here", "title here"), data={"priority": "high"})
    assert uut.check(e2) is True


def test_dupe_policy_mt_allows_different_message() -> None:
    delivery = Mock(name="tester")
    uut = DupeChecker({CONF_DUPE_POLICY: ATTR_DUPE_POLICY_MT})
    e1 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e1) is False
    e2 = Envelope(delivery, Notification(Mock(), "different message", "title here"))
    assert uut.check(e2) is False


def test_dupe_policy_none_never_suppresses() -> None:
    delivery = Mock(name="tester")
    uut = DupeChecker({CONF_DUPE_POLICY: ATTR_DUPE_POLICY_NONE})
    e1 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e1) is False
    e2 = Envelope(delivery, Notification(Mock(), "message here", "title here"))
    assert uut.check(e2) is False


class TestBoolify:
    def test_true_bool(self):
        assert boolify(True, default=False) is True

    def test_false_bool(self):
        assert boolify(False, default=True) is False

    def test_string_false_lowercase(self):
        assert boolify("false", default=True) is False

    def test_string_false_capitalized(self):
        assert boolify("False", default=True) is False

    def test_string_zero(self):
        assert boolify("0", default=True) is False

    def test_string_no(self):
        assert boolify("no", default=True) is False

    def test_string_off(self):
        assert boolify("off", default=True) is False

    def test_string_true(self):
        assert boolify("true", default=False) is True

    def test_string_yes(self):
        assert boolify("yes", default=False) is True

    def test_integer_one(self):
        assert boolify(1, default=False) is True

    def test_integer_zero(self):
        assert boolify(0, default=True) is False

    def test_empty_string(self):
        assert boolify("", default=True) is False

    def test_none_true(self):
        assert boolify(None, default=True)

    def test_none_false(self):
        assert not boolify(None, default=False)
