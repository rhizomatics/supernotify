
from custom_components.supernotify.common import CallRecord, ensure_dict, ensure_list, safe_extend, safe_get


def test_safe_get():
    assert safe_get(None, "foo") is None
    assert safe_get({}, "foo") is None
    assert safe_get({"foo": "fum"}, "foo") == "fum"


def test_safe_extend():
    assert safe_extend(None, None) == []
    assert safe_extend(1, 3) == [1, 3]
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
        "elapsed": 13.4
    }
