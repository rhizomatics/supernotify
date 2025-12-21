from unittest.mock import Mock

from custom_components.supernotify.common import CallRecord, DupeChecker, ensure_dict, ensure_list, safe_extend, safe_get
from custom_components.supernotify.envelope import Envelope
from custom_components.supernotify.notification import Notification


def test_safe_get():
    assert safe_get(None, "foo") is None
    assert safe_get({}, "foo") is None
    assert safe_get({"foo": "fum"}, "foo") == "fum"


def test_safe_extend():
    assert safe_extend(None, None) == []  # type:ignore[invalid-argument-type]
    assert safe_extend(1, 3) == [1, 3]  # type:ignore[invalid-argument-type]
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
    assert CallRecord(13.4, "switch", "toggle", {}, None, None).contents() == {
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
