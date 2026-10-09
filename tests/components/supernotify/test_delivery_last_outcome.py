"""`last_sent_at`, `last_outcome` and `last_skip_reason` on a delivery switch: when the delivery last
sent, and how the latest live notification went for it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.supernotify import DOMAIN
from custom_components.supernotify.const import DELIVERY_UNRECORDED_ATTRIBUTES
from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import EnvelopeOutcome

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.supernotify.engine import SupernotifyEngine

CHAT = "switch.supernotify_delivery_chat"
SPEAKER = "switch.supernotify_delivery_speaker"
LAST_ATTRS = ("last_sent_at", "last_outcome", "last_skip_reason")


def _delivery(action: str, **extra: Any) -> dict[str, Any]:
    return {"transport": "generic", "action": action, "target": ["testy.testy"], **extra}


async def _setup(hass: HomeAssistant, deliveries: dict[str, Any], failing: bool = False) -> SupernotifyEngine:
    async_mock_service(hass, "test", "chat")
    if failing:

        async def fail(_call: ServiceCall) -> None:
            raise HomeAssistantError("down")

        hass.services.async_register("test", "speaker", fail)
    else:
        async_mock_service(hass, "test", "speaker")
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"delivery": deliveries}})
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0].runtime_data


async def _notify(hass: HomeAssistant, message: str = "gate open", **data: Any) -> None:
    # generic deliveries aren't selected by default, so each test names the ones it sends through
    data.setdefault("delivery", ["chat", "speaker"])
    await hass.services.async_call(DOMAIN, "notify", {"message": message, **data}, blocking=True, return_response=True)
    await hass.async_block_till_done()


def _attrs(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    state = hass.states.get(entity_id)
    assert state is not None
    return dict(state.attributes)


async def test_nothing_shown_before_any_notification(hass: HomeAssistant) -> None:
    await _setup(hass, {"chat": _delivery("test.chat")})

    attrs = _attrs(hass, CHAT)
    for attr in LAST_ATTRS:
        assert attr not in attrs


async def test_sent(hass: HomeAssistant) -> None:
    await _setup(hass, {"chat": _delivery("test.chat")})

    await _notify(hass)

    attrs = _attrs(hass, CHAT)
    assert attrs["last_outcome"] == "success"
    assert attrs["last_sent_at"] is not None
    assert "last_skip_reason" not in attrs


async def test_skipped_keeps_last_sent_at(hass: HomeAssistant) -> None:
    await _setup(hass, {"chat": _delivery("test.chat")})
    await _notify(hass)
    sent_at = _attrs(hass, CHAT)["last_sent_at"]

    await _notify(hass)  # the same again, so a dupe

    attrs = _attrs(hass, CHAT)
    assert attrs["last_outcome"] == "skipped"
    assert attrs["last_skip_reason"] == "DUPE"
    assert attrs["last_sent_at"] == sent_at


async def test_skipped_by_a_delivery_condition(hass: HomeAssistant) -> None:
    hass.states.async_set("input_boolean.quiet", "off")
    await _setup(
        hass,
        {"chat": _delivery("test.chat", conditions={"condition": "state", "entity_id": "input_boolean.quiet", "state": "on"})},
    )

    await _notify(hass, delivery=["chat"])

    attrs = _attrs(hass, CHAT)
    assert attrs["last_outcome"] == "skipped"
    assert attrs["last_skip_reason"] == "DELIVERY_CONDITION"
    assert "last_sent_at" not in attrs


async def test_error_on_one_delivery_only(hass: HomeAssistant) -> None:
    # debug makes the call blocking, so the service's own error comes back to Supernotify
    await _setup(hass, {"chat": _delivery("test.chat"), "speaker": _delivery("test.speaker", debug=True)}, failing=True)

    await _notify(hass)

    assert _attrs(hass, CHAT)["last_outcome"] == "success"
    speaker = _attrs(hass, SPEAKER)
    assert speaker["last_outcome"] == "error"
    assert "last_sent_at" not in speaker
    assert "last_skip_reason" not in speaker


async def test_skip_reason_cleared_when_sent_again(hass: HomeAssistant) -> None:
    await _setup(hass, {"chat": _delivery("test.chat")})
    await _notify(hass)
    await _notify(hass)
    assert _attrs(hass, CHAT)["last_skip_reason"] == "DUPE"

    await _notify(hass, message="gate closed")

    attrs = _attrs(hass, CHAT)
    assert attrs["last_outcome"] == "success"
    assert "last_skip_reason" not in attrs


async def test_dry_run_leaves_them_alone(hass: HomeAssistant) -> None:
    await _setup(hass, {"chat": _delivery("test.chat")})
    await _notify(hass)
    before = {k: _attrs(hass, CHAT).get(k) for k in LAST_ATTRS}

    await _notify(hass, message="gate closed", dry_run="simulate")

    assert {k: _attrs(hass, CHAT).get(k) for k in LAST_ATTRS} == before


async def test_kept_out_of_history() -> None:
    assert set(LAST_ATTRS) <= DELIVERY_UNRECORDED_ATTRIBUTES


async def test_outcomes_from_notification_results(hass: HomeAssistant) -> None:
    engine = await _setup(hass, {"chat": _delivery("test.chat")})
    notification = Notification(engine.context, "hello")
    notification.deliveries = {
        "raised": {EnvelopeOutcome.SKIPPED: {"suppression_reason": "ERROR"}},
        "snoozed": {EnvelopeOutcome.SKIPPED: {"suppression_reason": "SNOOZED"}},
        "no_reason": {EnvelopeOutcome.SKIPPED: {"suppression_reason": "None"}},
    }

    assert notification.delivery_outcomes() == {
        "raised": (EnvelopeOutcome.ERROR, None),
        "snoozed": (EnvelopeOutcome.SKIPPED, "SNOOZED"),
        "no_reason": (EnvelopeOutcome.SKIPPED, None),
    }


async def test_unknown_delivery_name_is_ignored(hass: HomeAssistant) -> None:
    engine = await _setup(hass, {"chat": _delivery("test.chat")})
    notification = Notification(engine.context, "hello")
    notification.deliveries = {"!UNKNOWN!": {EnvelopeOutcome.SKIPPED: {"suppression_reason": "ERROR"}}}

    engine._record_delivery_outcomes(notification)

    assert "last_outcome" not in _attrs(hass, CHAT)
