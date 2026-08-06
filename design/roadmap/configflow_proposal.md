## Motivation

First concrete step for #60. SuperNotify is currently YAML-only, which HA flags as legacy and which raises the entry barrier for new users. This draft implements the smallest phase that moves the basics to the UI without touching deliveries, scenarios or the `notify.supernotify` contract - so the phasing discussion in #60 can happen on real code.

## Changes

- **config_flow.py** (new): `user` step (guided setup for a fresh install, no YAML required), one-shot **YAML import** (existing setups show up in the UI unchanged), and **reconfigure** flow for the global settings (paths, archive, dupe check window/policy, discovery toggles). Single entry enforced (`single_config_entry` + unique_id guard).
- **__init__.py**: config entry lifecycle. An entry imported from YAML only mirrors settings for the UI - the legacy notify platform keeps owning `notify.supernotify`, so there is no duplicate service and zero behaviour change for existing users. A UI-created entry loads the legacy notify platform via discovery, so a user with no YAML still gets `notify.supernotify`.
- **notify.py**: `async_get_service` now accepts config from the legacy YAML path *or* from a config entry via `discovery_info`; when starting from YAML it triggers the one-shot import. YAML artifacts that are not JSON-serializable (e.g. Jinja `Template` objects produced by schema validation) are converted to their source strings before being stored in the entry - otherwise the first entry update crashes with `Type is not JSON serializable: Template` (regression-tested).
- **manifest.json**: `config_flow: true`, `single_config_entry: true`.
- **strings.json + 11 translations** for the new steps (en, it, de, es, fr, hi, ja, nl, pl, pt, zh-Hans).
- **Tests**: `test_config_flow.py` (user / import / reconfigure / serialization regressions) and `test_init.py` (imported-entry lifecycle, options-update reload).

## Out of scope (by design, next phases)

Deliveries, scenarios, recipients and cameras stay YAML-only in this phase. The import keeps them in `entry.options` untouched so later phases can migrate them incrementally.

## Testing

- Full suite green with `pytest-homeassistant-custom-component` (user/import/reconfigure flows, serialization and update-listener regressions).
- Smoke-tested on a real HA install (2026.6.x, SuperNotify v1.16.2): YAML import -> entry appears as "SuperNotify (imported)", `notify.supernotify` unchanged, reconfigure form pre-filled and localized; deliveries keep working (Alexa announce verified end-to-end).
- `ruff check` / `ruff format` / `codespell` clean with the repo config.

## Scenarios Experiment

While waiting on the phased plan, I mapped my own (fairly large) scenario setup onto the "scenarios as helpers" idea to pressure-test it, and wanted to share what came out — it might be useful input.
TL;DR: out of 25 active scenarios, only 1 is actually a manual on/off switch. The other 24 are either auto-activating rules or already driven by helpers I created. So "scenario = a helper you toggle" fits a small minority; the rest are really configuration rules.
The breakdown:

17 auto-activating — triggered by message priority, time of day, date, occupancy, a sensor or the alarm panel. These have no meaningful on/off switch.
7 already driven by existing helpers — e.g. DND, guest mode, voice/phone/screen toggles. The input_boolean lever already exists; the scenario is just the rule that reads it.
1 manual (emergency, applied via apply_scenarios) — the only natural fit for a helper-style toggle.

A couple of concrete examples of why the rule doesn't fit inside a helper:
late_night — two conditions, a cross-midnight time template, a volume computed from an input_number, and a whisper effect:
yamllate_night:
  condition:
    - "{{ (notification_priority | default('medium')) not in ['critical','high'] }}"
    - >-
      {% set t = now().strftime('%H:%M:%S') %}
      {% set start = states('input_datetime.notifier_start_late_night') %}
      {% set end = states('input_datetime.notifier_start_early_morning') %}
      {{ (start <= end and t >= start and t < end) or (start > end and (t >= start or t < end)) }}
  delivery:
    alexa_announce:
      data:
        volume: "{{ (states('input_number.notifier_late_night_volume') | float(20)) / 100 }}"
        message_template: '<amazon:effect name="whispered">{{ notification_message }}</amazon:effect>'
dnd_workdays crosses four entities (an input_boolean, two input_datetime, a binary_sensor). That logic has to live somewhere as config — it can't be an entity state.
Also worth noting: the helpers are already the control surface here — the time bands (input_datetime), the per-band volumes (input_number), the DND/guest toggles (input_boolean). They work great as inputs referenced by scenarios.
What this suggests (just my read, very open to yours):

Scenario definitions (conditions + delivery overrides) → subentries, since they're rules, not switches.
Helpers → stay as the levers, referenced from the subentry flow via entity selectors (which is already how my setup works).
Optionally expose each scenario as a read-only state entity for dashboards/debugging (like the existing sensor.notifier_whisper_attivo) — that's the "helper-ish" part that does make sense.
Only the genuinely manual ones (emergency, a future "holiday/party mode") get a dedicated toggle helper.

The risk I'd want to avoid is forcing all scenarios into toggle-helpers, which would break the automatic behaviour (time/priority/occupancy) that's the core of the system.
Happy to share the full scenario-by-scenario mapping if useful. Curious how this lines up with the plan you put together.
