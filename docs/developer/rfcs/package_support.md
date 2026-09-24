# Package Support

Changes needed in Supernotify before any [Package](./packages.md) is built, collected from the proposed packages:
[Frigate](./frigate_supernotifier.md), appliance Live Activities (smart and power monitored), and motion sensors.

Packages are built as modules inside Supernotify, set up as config subentries. A thin HACS repository per package,
for example *Frigate SuperNotifier*, can come later purely so people searching HACS find it; it would only guide
the user to install or enable Supernotify.

## Needs by Package

| Upgrade                                   | Frigate | Appliance Live Activity | Power Monitored | Motion |
| ----------------------------------------- | :-----: | :---------------------: | :-------------: | :----: |
| 1. Snooze enforcement                     |    ●    |                         |                 |   ●    |
| 2. Notification source                    |    ●    |            ●            |        ●        |   ●    |
| 3. Notification lifecycle and tag         |    ●    |            ●            |        ●        |        |
| 4. Cooldown per source                    |    ●    |                         |                 |   ●    |
| 5. Scenario priority                      |    ○    |                         |                 |   ●    |
| 6. Mobile push media precedence           |    ●    |                         |                 |   ○    |
| 7. iOS video attachment                   |    ●    |                         |                 |        |
| 8. Tap URL                                |    ●    |            ○            |        ○        |   ○    |
| 9. Live view entity                       |    ●    |                         |                 |   ○    |
| 10. Live Activity fields                  |    ○    |            ●            |        ●        |        |
| 11. Package framework                     |    ●    |            ●            |        ●        |   ●    |
| 12. Stored notification action            |    ●    |            ●            |        ●        |   ●    |
| 13. Richer `services.yaml`                |    ●    |            ●            |        ●        |   ●    |
| 14. Optional integration dependencies     |    ●    |            ●            |                 |        |

● needed, ○ useful

## Fixes

### 1. Snooze enforcement

`SUPERNOTIFY_SNOOZE_EVERYONE_CAMERA_*` snoozes, from the button mobile push adds to every camera notification, are
recorded but appear not to be applied. `Snoozer.is_global_snooze()` only checks `EVERYTHING` and `NONCRITICAL`, and
`Snoozer.filter_recipients()` only acts on user-scoped snoozes, so everyone-scoped camera, delivery, transport and
priority snoozes have no effect. Camera snoozes also need the notification's camera to compare with.

Confirm with a regression test first.

## Notification Model

### 2. Notification source

A `source` field on `supernotify.notify`, such as `frigate:driveway` or `appliance:dishwasher`, carried into the
archive, debug trace and scenario condition variables. Lets users write scenarios for one package or one camera without
matching message text, and gives cooldown, snoozing and lifecycle something to key on. Packages set it; automations can
too.

### 3. Notification lifecycle and tag

Promote `mobile_push_notification_tag` to a transport-neutral `tag`, and add a `lifecycle` of `new` (default), `update`
or `end`:

- **update** - replaces the earlier notification with the same tag without alerting again. Mobile push replaces
  silently (iOS `sound: none` and `passive`, Android `alert_once`); email and spoken transports skip updates by default
- **end** - mobile push sends `clear_notification` for the tag, or a final silent update if the package wants the
  result to stay visible; other transports send a normal notification, such as "Dishwasher finished"
- Duplicate checking treats a changed update of the same tag as new, rather than suppressing it

This replaces the Live Activity recipe's per-delivery `clear_notification` message and `delivery_selection: fixed`.

### 4. Cooldown per source

Minimum time between `new` notifications from the same source, as the Frigate blueprint's `cooldown`. Updates and ends
of a tag already sent aren't limited. A first step toward the Rate Limiting roadmap item.

### 5. Scenario priority

Let a scenario set the notification's priority, not just a delivery's `data.priority`, so a motion package can have
"armed and night" raise to `high` and "occupied and not dangerous" drop to `low`. The priority then has to be settled
before delivery selection, while scenario conditions can themselves use priority - so a scenario's priority applies
after scenarios are chosen and doesn't re-trigger selection. Relates to *Per-delivery Priority* on the
[Roadmap](../roadmap.md).

## Mobile Push

### 6. Media precedence

With both `camera_entity_id` and `snapshot_url`, the camera grab currently wins. Frigate needs the snapshot URL for the
image, with the camera entity used only for live view, grouping and snoozing. Use `snapshot_url` for the image when given,
and only grab from the camera without one.

### 7. iOS video attachment

`clip_url` only becomes Android's `video`. Add the iOS `attachment` with `url` and a `content-type` derived from the URL
(`application/vnd.apple.mpegurl` for `.m3u8`). An option to leave out `.mp4` clips for Apple devices builds in the
[Frigate Apple fix](../../recipes/fix_frigate_apple_push.md), so it no longer needs `data_keys_select`.

### 8. Tap URL

A cross-platform URL opened when the notification is tapped, becoming iOS `url` and Android `clickAction`. Today it only
works as passthrough `extra_data`, which can't differ per platform.

### 9. Live view entity

Set the iOS live camera view (`entity_id`) independently of where the image comes from.

### 10. Live Activity fields

First-class fields for [Live Activities](https://companion.home-assistant.io/docs/notifications/live-activities):
`live_update`, `progress`, `progress_max`, `chronometer`, `when` and the notification icon, mapped for iOS and Android,
and left out entirely when the source value is `unavailable`. Combined with lifecycle `update` and `end`, an appliance
package only needs to send the current state.

## Package Framework

### 11. Package modules and subentries

- A `packages` sub-package with a base class per package: `detect(hass)`, a subentry flow, default notification,
  and runtime start and stop hooks for listeners
- Each package is a config subentry type of the Supernotify entry, so it appears as *Add Frigate notifications* on the
  integration page. Needs HA config subentries, which the current minimum Home Assistant version supports
- Discovery: on startup, a package that detects something it could handle raises a fixable repair issue offering to set
  it up. Repairs' own *Ignore* gives the "don't ask again" behaviour without new storage
- Packages run inside Supernotify, so they're loaded, reloaded and unloaded with the config entry

### 12. Stored notification action

Each subentry keeps its notification as an action sequence, edited with the `ActionSelector`, pre-filled with a
`supernotify.notify` call, and run with `helpers.script.Script` with the package's variables. The core Template helper
already uses `ActionSelector` in its config flow. Also needs:

- a *Reset to default* option, so users can pick up improved defaults
- validation on load, raising a repair issue if a stored action no longer matches the `supernotify.notify` schema
- spikes: that defaults show pre-filled in a subentry flow and templates survive storage, and that `ConditionSelector`
  works in a config flow, since no core integration uses it there yet

### 13. Richer `services.yaml`

The action editor becomes the whole customization UI for packages, so `supernotify.notify` field descriptions, examples
and selectors matter far more, including dynamic delivery and scenario dropdowns via `async_set_service_schema`, and
translations for all of it.

### 14. Optional integration dependencies

Packages bundled in Supernotify can't add `mqtt` or `frigate` to `dependencies`, since that would force them on every
user. Add them to `after_dependencies` instead, check at runtime, and only offer a package when its integrations are
loaded.

## Suggested Order

1. **Snooze enforcement** - a bug today, small, and packages depend on it
2. **Mobile push media, iOS video, tap URL, live view** (6-9) - self-contained and useful to existing Frigate blueprint users
3. **Source, lifecycle and tag, cooldown** (2-4) - the core model packages build on
4. **Live Activity fields** (10) - makes the existing dishwasher recipe much simpler
5. **Scenario priority** (5)
6. **Package framework, stored action and `services.yaml`** (11-14), after the spikes, then the first package
