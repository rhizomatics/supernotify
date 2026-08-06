# ConfigFlow Implementation Approach

## Principles

The design decisions, difficulties and work break down into these groups:

1. Straightforward
  - Set up a working Supernotify purely from UI
  - `minimal.yaml` setup is almost there
  - Extra config pages for more advanced options like `archive`,`dupe_check`,`housekeeping`
2. More Complex But Necessary
  - Other than the auto generated default deliveries, these are essential to useful notifications
  - Cameras may fall into this
  - Solution needed for the more loosely defined `options` that isn't just free text
3. Advanced and Less Clear HA Construct
  - Scenarios may work as helpers
  - Condition editing may need work or be hampered by internal HA APIs
  - Advanced concept, and ability to edit multiple as free-form YAML more of a benefit
4. More obscure, less benefit from being in UI
  - Action Groups, Links (latter could be culled)

The approach should enable #1 and #2 without having to solve for #3 or do the work for #4, and keep options open for the latter.

Top-level config should be entirely ConfigEntry, and automatically migrated from existing YAML, with old YAML deprecated

Deliveries, Transports, Scenarios and Recipients should be maintained as YAML, in a similar fashion to how HA treats automations - where UI editing is available, it results in updates to YAML, and YAML changes are exposed via the UI editing.
