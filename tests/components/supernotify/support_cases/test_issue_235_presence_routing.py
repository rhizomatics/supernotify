"""Regression test for GitHub issue #235 - presence-dependent delivery with fallback

https://github.com/rhizomatics/supernotify/issues/235

Reporter wanted: notify whoever's home, and notify everyone if nobody's home. Built it with
one delivery per person, gated by a `conditions:` state check on that person's own Person
entity, plus a third delivery meant as the "nobody home" catch-all, given `inclusion:
[scenario, fallback]`. Two things went wrong, both config mistakes rather than bugs:

1. Each per-person delivery's `target:` used dotted `notify.mobile_app_<x>` syntax, e.g.
   `notify.mobile_app_phone_alex`. That's the service call form used by the `notify_entity`
   transport (see docs/transports/notify_entity.md) - everywhere else (docs/usage/targets.md,
   docs/configuration/people.md), a `mobile_app_id` target is the bare value,
   `mobile_app_phone_alex`. The dotted form isn't recognised as a `mobile_app_id`, so the
   delivery's own `target:` never resolves to anything on its own. The default
   `target_usage: no_action` then means the delivery's only *other* target source -
   `default_person_ids()`, which (with no `occupancy` set, i.e. the "all" default) expands to
   *every* recipient regardless of presence - fills in by accident, notifying every mobile
   device of every recipient rather than just the one named phone.

2. `inclusion: [scenario, fallback]` does not mean "last resort, only if nothing else
   delivered" *within* this scenario. `fallback` only wires a delivery into a separate,
   scenario-independent mechanism that fires when literally nothing delivered for the whole
   notification (see `fallback_by_default_deliveries` / `Notification.deliver()`). Because
   the scenario's own `delivery:` map names this delivery directly, it's unconditionally
   selected and attempted like any other scenario delivery - and since it has no `occupancy`
   or `conditions` of its own, there's nothing to stop it firing every time.

The fix needs no code change, just correct config. Two ways to get there:

- CORRECTED_YAML: `target_usage: fixed` plus a bare `mobile_app_id` value locks each personal
  delivery to exactly its own configured device, bypassing recipient-based expansion
  entirely. `occupancy: all_out` on the catch-all delivery gates it - for a fixed-target
  delivery, per docs/configuration/deliveries.md, `occupancy` decides whether the whole
  delivery fires at all - so it only fires when every recipient is away. Still needs one
  delivery block per person.

- SIMPLIFIED_YAML: skip per-person deliveries altogether and let `occupancy` do the
  recipient narrowing. `PeopleRegistry.filter_recipients_by_occupancy()` (people.py) treats
  `only_in`/`only_out` specially - they return *only* the narrowed subset of recipients
  (home people for `only_in`, everyone for `all_out` when all are away), unlike
  `any_in`/`any_out`, which just gate on whether *any* recipient matches but still resolve to
  *everyone*. So a single delivery with `occupancy: only_in` and no fixed `target:` at all
  resolves - via the normal recipient-to-device path - to just whoever's home, each on their
  own device(s). A second delivery with `occupancy: all_out`, also with no target, covers
  the "nobody home" case the same way. Adding a third recipient needs no config changes -
  neither delivery names a person. The caveat: it notifies a person on *all* their
  registered devices, not one specific named phone the way CORRECTED_YAML's fixed target
  does - if a reporter genuinely wants exactly one of several devices, this simpler form
  can't express that and the per-person fixed-target version is still needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from custom_components.supernotify.notification import Notification
from custom_components.supernotify.schema import EnvelopeOutcome
from custom_components.supernotify.transports.mobile_push import MobilePushTransport
from tests.components.supernotify.hass_setup_lib import TestingContext, first_envelope, register_mobile_app

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# as originally reported: a dotted `notify.mobile_app_<x>` target, and the fallback delivery
# is only `inclusion: [scenario, fallback]` with no occupancy/conditions of its own
REPORTED_YAML = """
    recipients:
      - person: person.alex
      - person: person.sam
    delivery:
      presence_alex:
        transport: mobile_push
        inclusion:
          - scenario
        target:
          - notify.mobile_app_phone_alex
        conditions:
          condition: state
          entity_id: person.alex
          state: home
      presence_sam:
        transport: mobile_push
        inclusion:
          - scenario
        target:
          - notify.mobile_app_phone_sam
        conditions:
          condition: state
          entity_id: person.sam
          state: home
      presence_fallback_all:
        transport: mobile_push
        inclusion:
          - scenario
          - fallback
        target:
          - notify.mobile_app_phone_alex
          - notify.mobile_app_phone_sam
    scenarios:
      presence_dependent:
        alias: "Presence dependent"
        delivery:
          presence_alex:
          presence_sam:
          presence_fallback_all:
"""

# corrected: bare mobile_app_id values with target_usage: fixed lock each delivery to its own
# device, and occupancy: all_out gates the catch-all to only when everyone's away
CORRECTED_YAML = """
    delivery_control:
      default_inclusion: explicit
    recipients:
      - person: person.alex
      - person: person.sam
    delivery:
      presence_alex:
        transport: mobile_push
        inclusion:
          - scenario
        target_usage: fixed
        target:
          - mobile_app_phone_alex
        conditions:
          condition: state
          entity_id: person.alex
          state: home
      presence_sam:
        transport: mobile_push
        inclusion:
          - scenario
        target_usage: fixed
        target:
          - mobile_app_phone_sam
        conditions:
          condition: state
          entity_id: person.sam
          state: home
      presence_fallback_all:
        transport: mobile_push
        inclusion:
          - scenario
          - fallback
        target_usage: fixed
        occupancy: all_out
        target:
          - mobile_app_spare_alex
          - mobile_app_phone_alex
          - mobile_app_phone_sam
    scenarios:
      presence_dependent:
        alias: "Presence dependent"
        delivery:
          presence_alex:
          presence_sam:
          presence_fallback_all:
"""

# simplified: no per-person deliveries at all. `only_in`/`all_out` occupancy narrows the
# recipient-resolved target to just who's home (or everyone, if nobody is) - scales to any
# number of recipients with no config changes, at the cost of notifying every one of a
# person's own devices rather than a single named one
SIMPLIFIED_YAML = """
    delivery_control:
      default_inclusion: explicit
    recipients:
      - person: person.alex
      - person: person.sam
    delivery:
      presence_home:
        transport: mobile_push
        inclusion:
          - scenario
        occupancy: only_in
      presence_fallback_all:
        transport: mobile_push
        inclusion:
          - scenario
          - fallback
        occupancy: all_out
    scenarios:
      presence_dependent:
        alias: "Presence dependent"
        delivery:
          presence_home:
          presence_fallback_all:
"""


async def _build_context(hass: HomeAssistant, yaml: str) -> TestingContext:
    from homeassistant.components import person
    from homeassistant.setup import async_setup_component

    # person entities must exist before supernotify validates its delivery conditions at
    # startup, same as a real install where the person integration loads ahead of supernotify
    await async_setup_component(hass, "person", {})
    await person.async_create_person(hass, "Alex")
    await person.async_create_person(hass, "Sam")
    await hass.async_block_till_done()

    ctx = TestingContext(
        homeassistant=hass,
        components={"person": {}},
        viable_transport_types=[MobilePushTransport],
        yaml=yaml,
    )
    # devices must be registered before test_initialize() builds the people registry, same as
    # a real install where mobile_app devices are already paired by the time supernotify loads
    # - Alex has two devices, same as the reporter's install, to show the over-notification
    register_mobile_app(ctx.hass_api, person="person.alex", device_name="spare_alex")
    register_mobile_app(ctx.hass_api, person="person.alex", device_name="phone_alex")
    register_mobile_app(ctx.hass_api, person="person.sam", device_name="phone_sam")
    await ctx.test_initialize()
    return ctx


@pytest.fixture
async def reported_config(hass: HomeAssistant) -> TestingContext:
    ctx = await _build_context(hass, REPORTED_YAML)
    hass.states.async_set("person.alex", "home")
    hass.states.async_set("person.sam", "not_home")
    return ctx


@pytest.fixture
async def corrected_config(hass: HomeAssistant) -> TestingContext:
    ctx = await _build_context(hass, CORRECTED_YAML)
    hass.states.async_set("person.alex", "home")
    hass.states.async_set("person.sam", "not_home")
    return ctx


@pytest.fixture
async def simplified_config(hass: HomeAssistant) -> TestingContext:
    ctx = await _build_context(hass, SIMPLIFIED_YAML)
    hass.states.async_set("person.alex", "home")
    hass.states.async_set("person.sam", "not_home")
    return ctx


async def test_reported_config_notifies_every_device_not_just_the_configured_one(
    reported_config: TestingContext, hass: HomeAssistant
) -> None:
    """The dotted `notify.mobile_app_phone_alex` target never resolves, so recipient-based
    expansion fills in instead - reaching Alex's other phone, and even Sam's, although
    they're away and not the delivery this is meant to be."""
    uut = Notification(reported_config, "Test presence dependent", action_data={"apply_scenarios": ["presence_dependent"]})
    await uut.initialize()
    await uut.deliver()
    await hass.async_block_till_done()

    envelope = first_envelope(uut, "presence_alex")
    assert envelope.target.as_dict() == {
        "mobile_app_id": ["mobile_app_spare_alex", "mobile_app_phone_alex", "mobile_app_phone_sam"],
        "person_id": ["person.alex", "person.sam"],
    }


async def test_reported_config_fallback_fires_even_though_someone_is_home(
    reported_config: TestingContext, hass: HomeAssistant
) -> None:
    """`inclusion: fallback` alone doesn't make this "last resort" - with no occupancy or
    conditions of its own, and explicitly listed in the scenario, it always fires."""
    uut = Notification(reported_config, "Test presence dependent", action_data={"apply_scenarios": ["presence_dependent"]})
    await uut.initialize()
    await uut.deliver()
    await hass.async_block_till_done()

    assert EnvelopeOutcome.SUCCESS in uut.deliveries["presence_fallback_all"]


async def test_corrected_config_notifies_only_the_person_at_home_on_their_own_device(
    corrected_config: TestingContext, hass: HomeAssistant
) -> None:
    uut = Notification(corrected_config, "Test presence dependent", action_data={"apply_scenarios": ["presence_dependent"]})
    await uut.initialize()
    await uut.deliver()
    await hass.async_block_till_done()

    envelope = first_envelope(uut, "presence_alex")
    assert envelope.target.as_dict() == {"mobile_app_id": ["mobile_app_phone_alex"]}

    assert uut.deliveries["presence_sam"][EnvelopeOutcome.SKIPPED]["suppression_reason"] == "DELIVERY_CONDITION"  # type: ignore
    assert uut.deliveries["presence_fallback_all"][EnvelopeOutcome.SKIPPED]["suppression_reason"] == "OCCUPANCY"  # type: ignore


async def test_corrected_config_falls_back_to_everyone_when_nobody_home(
    corrected_config: TestingContext, hass: HomeAssistant
) -> None:
    hass.states.async_set("person.alex", "not_home")

    uut = Notification(corrected_config, "Test presence dependent", action_data={"apply_scenarios": ["presence_dependent"]})
    await uut.initialize()
    await uut.deliver()
    await hass.async_block_till_done()

    assert "presence_alex" not in uut.deliveries or EnvelopeOutcome.SUCCESS not in uut.deliveries["presence_alex"]
    assert "presence_sam" not in uut.deliveries or EnvelopeOutcome.SUCCESS not in uut.deliveries["presence_sam"]

    envelope = first_envelope(uut, "presence_fallback_all")
    assert envelope.target.as_dict() == {
        "mobile_app_id": ["mobile_app_spare_alex", "mobile_app_phone_alex", "mobile_app_phone_sam"]
    }


async def test_simplified_config_notifies_only_the_person_at_home_on_all_their_devices(
    simplified_config: TestingContext, hass: HomeAssistant
) -> None:
    """Caveat versus CORRECTED_YAML: `occupancy: only_in` narrows by *recipient*, not by
    device - Alex gets notified on both their phones, not just one named one."""
    uut = Notification(simplified_config, "Test presence dependent", action_data={"apply_scenarios": ["presence_dependent"]})
    await uut.initialize()
    await uut.deliver()
    await hass.async_block_till_done()

    envelope = first_envelope(uut, "presence_home")
    assert envelope.target.as_dict() == {
        "mobile_app_id": ["mobile_app_spare_alex", "mobile_app_phone_alex"],
        "person_id": ["person.alex"],
    }
    assert uut.deliveries["presence_fallback_all"][EnvelopeOutcome.SKIPPED]["suppression_reason"] == "OCCUPANCY"  # type: ignore


async def test_simplified_config_falls_back_to_everyone_when_nobody_home(
    simplified_config: TestingContext, hass: HomeAssistant
) -> None:
    hass.states.async_set("person.alex", "not_home")

    uut = Notification(simplified_config, "Test presence dependent", action_data={"apply_scenarios": ["presence_dependent"]})
    await uut.initialize()
    await uut.deliver()
    await hass.async_block_till_done()

    assert uut.deliveries["presence_home"][EnvelopeOutcome.SKIPPED]["suppression_reason"] == "OCCUPANCY"  # type: ignore

    envelope = first_envelope(uut, "presence_fallback_all")
    assert envelope.target.as_dict() == {
        "mobile_app_id": ["mobile_app_spare_alex", "mobile_app_phone_alex", "mobile_app_phone_sam"],
        "person_id": ["person.alex", "person.sam"],
    }
