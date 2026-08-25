# ConfigFlow Implementation Approach

## Goals

- Make Supernotify more accessible to more users, including non-technical ones who will never use YAML. Supernotify should itself make HomeAssistant more accessible, for example by simplifying mobile push setup.
- Align with Home Assistant architecture and vision
- Move towards Platinum quality scale level
- Remove friction for Supernotify upgrades, especially where YAML is migrated or deprecated
- Continue to support advanced users who can more efficiently write and edit complex configurations in text
- Support use of GenAI agents to manage config and notifications

## Principles

The design decisions, difficulties and work break down into these groups:

1. Straightforward **Completed in v2.0.0**
  - Set up a working Supernotify purely from UI
  - `minimal.yaml` setup is almost there
  - Extra config pages for more advanced options like `archive`,`dupe_check`,`housekeeping`
2. More Complex But Necessary
  - Other than the auto generated default deliveries, these are essential to useful notifications
  - Cameras may fall into this
  - Solution needed in ConfigFlow UI for the more loosely defined delivery `options` that isn't just free text
3. Advanced and Less Clear HA Construct
  - Scenarios don't have obvious direct place in HA concepts/UI, complications with use as helpers
  - Scenarios also may need refactored
   - Simpler ones that are capable of being moved to UI (like the simple toggle ones)
   - More complex ones that resist it (or are agent managed in code).
   - Solve Jinja `Template` objects produced by schema validation artifacts that are not JSON-serializable
  - Possible half-way house of having UI views of YAML defined scenarios, with some simple UI to enable/disable
  - Condition editing may need work or be hampered by internal HA APIs
  - Advanced concept, and ability to edit multiple as free-form YAML more of a benefit
4. More obscure, less benefit from being in UI
  - Action Groups, Links (latter could be culled)

The approach should enable #1 and #2 without having to solve for #3 or do the work for #4, and keep options open for the latter.

All config is either ConfigEntry based or round-tripped YAML.  No dual config.

Top-level config should be entirely ConfigEntry. The first ConfigFlow version of the plugin should automatically migrate existing YAML, and raise repairs for the old core YAML and any subsequent core YAML. If possible automate the repair, so YAML rewritten to omit the deprecated config, when user decides comfortable to keep with new version (may need ruamel.yaml).

Landed for the Immediate phase as a *mirror*, not a full cutover: an existing YAML config gets a one-shot import into a ConfigEntry (visible in the UI, editable via the same reconfigure/options flows a UI-only install gets), and a `deprecated_yaml` repair nags on every YAML load until it's removed - but the legacy YAML platform keeps owning `notify.supernotify` for these entries, so editing the mirrored entry does not yet change runtime behaviour. Full cutover (the entry becoming authoritative, editing it actually doing something) waits until Delivery/Transport/Scenario/Recipient/Camera also move off YAML in the Third phase - doing it earlier would mean deliveries silently stop working the moment someone touches the UI, which is worse than the mirror being cosmetic-only in the meantime. YAML-rewrite automation (ruamel.yaml) is not implemented - still deferred.

Deliveries, Transports, Scenarios and Recipients should be maintained as YAML, in a similar fashion to how HA treats automations - where UI editing is available, it results in updates to YAML, and YAML changes are exposed via the UI editing. Testing needs improved for Scenario before major changes.

Balance moving up the Quality Scale over focusing solely on the purely config flow phases, for example handling of runtime data and async processing.

**Notify Entity decision:** recent changes to HA (Notify Entities, and their extension to SMTP) raised the question of whether Supernotify should migrate off `BaseNotificationService` entirely. Decided not to, for now - a full NotifyEntity rewrite isn't trusted yet and is a bigger, separate piece of work. Instead the Immediate phase moves *off* the legacy notify-platform discovery/`config_per_platform` machinery (the actual "legacy" part) while keeping `BaseNotificationService` itself: `async_setup_entry` calls `BaseNotificationService.async_setup`/`async_register_services` directly, with no `discovery.async_load_platform` indirection. `notify.supernotify` stays a `BaseNotificationService`-registered action. Revisit NotifyEntity as its own phase if ever pursued.

## Phasing

### Immediate

**Completed in v2.0.0**

Implement the 'Straightforward' group, its low risk, has minimal impact on solving the rest of the design and opens up functionality like auto device discovery and delivery generation to users who will never touch YAML.

Breakdown:

* `user` step (zero required fields, matches `minimal.yaml`)
* `reconfigure` step for editing those same global settings post-setup
* Options flow for `archive`/`dupe_check`/`housekeeping`
* YAML mirror-import
* `deprecated_yaml` repair

### Second

* Solve the remaining Bronze and Silver level quality issues that don't impinge on how delivery/transport/scenario/recipient/camera are resolved.   - The Notify Entity question from the Principles section above is resolved (staying on `BaseNotificationService`)
- Remaining Second-phase work is entity/service lifecycle quality-scale items (see `quality_scale.yaml`'s `action-setup` for the still-YAML-only supplemental `supernotify.*` debugging services), not an architecture decision.

### Third

* Upgrade to Gold level quality.
* Move Delivery, Transport, Recipient and Camera to ConfigFlow.
  - This may mean that the UI supports only a simplified version of these, if for example Condition editing is not viable, and the YAML remains. Preferably every one of these can be edited in either the UI or YAML, and round-tripped between them.
* Extend auto discovery to other viable transports
  - ntfy, gotify, telegram, pushover, lametric, alexa devices, SMS (if mikrotik_sms, twilio, clicksend etc installed)

### Fourth

* Implement some UI for Scenarios, at least view/enable/disable

### Later, Maybe Never

* Move ActionGroups, Links out of YAML and complete Scenarios.
* Upgrade to Platinum level quality.
* Review and implement alignment with Notify Entity architecture.
* Review Recipient as a HA entity
* Complete implementation of Actions, Action Groups and Links
