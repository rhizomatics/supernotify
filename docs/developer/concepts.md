---
tags:
  - developer
  - envelope
  - transport
  - delivery
  - target
description: Technical Concepts for Supernotify
---
# Developer Concepts

These build on the user-facing [Core Concepts](../concepts.md), describing how the pieces fit together inside the code. For the classes themselves, see [Classes](classes/index.md) and the [Class Diagram](class_diagram.md).

## How a Notification Flows

Each `supernotify.notify` action call goes through the same stages, driven by `SupernotifyEngine` and
`Notification`:

1. **Create** - the engine builds a `Notification` from the action call's message, title, target and `data`
2. **Pick scenarios** - occupancy is worked out, `ConditionVariables` built, and scenarios chosen from those
   named in `apply_scenarios` plus those whose `conditions` match, then narrowed by any `constrain_scenarios`.
   If `require_scenarios` is set and none are active, the notification is suppressed with `NO_SCENARIO`
3. **Select deliveries** - see [Delivery Selection](#delivery-selection). A global snooze suppresses the
   notification here with `SNOOZED`
4. **Apply scenarios** - media and action groups from the active scenarios are merged in
5. **Schedule** - deliveries run concurrently. Where a camera is configured, deliveries whose transport has
   the `SNAPSHOT_IMAGE` feature are deferred, so the image grab (and any PTZ movement) runs alongside
   the immediate deliveries, such as chimes and TTS
6. **Per delivery** - each delivery is checked for a disabled transport, a priority mismatch and failed
   delivery conditions; then targets are generated, split into [Envelopes](#envelope), each envelope is [checked for duplicates](#duplicate-detection), and finally handed to the transport
7. **Fallback** - if nothing was delivered, deliveries with `inclusion: fallback` are called when there was no error, and `inclusion: fallback_on_error` ones when a delivery failed
8. **Archive** - the notification, with its envelopes, goes to the
   [archive](../configuration/archiving.md)

## Transport Adaptors

A regular Home Assistant Notify Group seems to allow multi-channel notifications, but each notify integration has different `data` (and `data` inside `data`!) structures and addressing, so in practice group notifications get cut down to the lowest common set of attributes, like just `message`.

Each Supernotify `Transport` class is an adaptor for one of these integrations. It prunes out attributes the integration can't accept, reshapes `data`, picks out the targets it can use, and applies transport-level defaults, so a single notification can go to many mutually incompatible platforms.

### Transport Features

Each transport declares what it can handle as `TransportFeature` flags: `MESSAGE`, `TITLE`, `IMAGES`, `VIDEO`, `ACTIONS`, `TEMPLATE_FILE`, `SNAPSHOT_IMAGE`, `SPOKEN` and `SOUND`. These decide how content is trimmed for the transport, whether a delivery is deferred for an image grab, and whether a spoken form of the message is used for duplicate checking.

## Delivery Provenance and Auto-Configuration

At startup, each transport is checked with `Transport.is_viable()`, for example whether the integration it wraps is installed, and only viable transports build their standard deliveries. Once all configured and standard deliveries are known, any transport left with no deliveries at all is unloaded.

Every `Delivery` records where it came from, as `DeliveryProvenance`:

| Provenance         | Meaning                                                                                         |
| ------------------ | ----------------------------------------------------------------------------------------------- |
| `DEFAULT_STANDARD` | The auto-configured delivery with the same name as its transport, like `email`                  |
| `EXTRA_STANDARD`   | Other deliveries a transport creates for itself, like `alexa_devices_announce_all` or chime aliases |
| `CONFIG`           | Defined in the user's configuration, which overrides a standard delivery of the same name       |

`Transport.inclusion_mode` sets the `inclusion` of auto-configured deliveries. Most are `explicit`, only firing when asked for; the few that can sensibly fire on every notification, such as email, mobile push, SMS and Notify Entity, use `default`.

## Delivery Selection

A notification's deliveries are the union of:

- Deliveries enabled by active scenarios
- Deliveries with `inclusion: default` (unless the call uses fixed delivery selection)
- Deliveries enabled in the action call's `delivery` block
- Deliveries a recipient has enabled for themselves, which then only target that recipient

less any disabled by a scenario or the call. The action call wins where it re-enables a delivery a scenario disabled.

The result is ordered by each delivery's `selection_rank`: `FIRST`, then `ANY`, then `LAST` - with configured `LAST` deliveries ahead of auto-configured ones. This order matters for [Target Claiming](#target-claiming).

## Target Claiming

Targets are categorized when a `Target` is built, either automatically (e-mail, phone, entity, device, mobile app) or by a category prefix or mapping. Area, floor and label targets are resolved to entities, with groups expanded, before any delivery selects from them.

Each direct target is claimed once, by the first delivery in selection order that accepts its category, so the same e-mail address isn't sent by both `plain_email` and `html_email`. A delivery's own `target` config is scoped only to it, so there `Delivery.reclassify_unqualified_target()` can claim values that didn't match any category for that delivery's transport.

What's left over is recorded in the archive:

- `uncategorized_targets` - couldn't be categorized, so were ignored
- `unassigned_targets` - were categorized, but no selected delivery took them

`target_select` and similar include/exclude options share one mechanism, `SelectionRule`, and data
filtering uses `DataFilter`.

## Envelope

An `Envelope` is a notification customized for one delivery:

- List of targets is filtered, for example only e-mail addresses for the SMTP integration
- Indirect targets, like `person.xxx`, are materialized into e-mail addresses, phone numbers and so on
- The `data` section may have been customized by the delivery definition, by a scenario or target specific data

A delivery can produce more than one envelope, for example where targets carry their own `data`, so each set of targets with uniquely crafted `data` get their own Envelope.
Envelopes don't appear in configuration; users only see them in an
[archived notification](../configuration/archiving.md), which keeps a list of *delivered* and *undelivered* envelopes.

## Duplicate Detection

Duplicate checking is done per envelope by `DupeChecker`, using a hash of the message and title (stripped of digits and punctuation, so timestamps and counters don't defeat it), the delivery name, the resolved targets and the camera or media URL. Hashes are kept in a short-lived cache, and the default policy treats a repeat as a duplicate only if an earlier copy had the same or higher priority. See
[Duplicate Detection](../configuration/dupe_detection.md) for the user settings.

## Suppression Reasons

When a delivery doesn't go out, the reason is recorded as a `SuppressionReason`:

| Reason                | Cause                                                          |
| --------------------- | -------------------------------------------------------------- |
| `SNOOZED`             | Snoozed or silenced                                            |
| `DUPE`                | Duplicate of a recent notification                             |
| `NO_SCENARIO`         | `require_scenarios` set, but none active                       |
| `NO_ACTION`           | No action to call                                              |
| `NO_TARGET`           | Transport requires a target, and none were resolved            |
| `INVALID_ACTION_DATA` | Action call `data` failed validation                           |
| `TRANSPORT_DISABLED`  | The delivery's transport is switched off                       |
| `PRIORITY`            | Notification priority not in the delivery's `priority` list    |
| `DELIVERY_CONDITION`  | The delivery's `conditions` didn't match                       |
| `ERROR`               | Unexpected exception                                           |
| `UNKNOWN`             | The transport declined without a specific reason               |

## Debug Trace

Each notification carries a `DebugTrace`, which records every stage of delivery selection (including which scenario, recipient, default or call enabled or disabled each delivery) and every step of target generation per delivery, as numbered stages like `100_delivery_default_fixed`. It's written to the archive when diagnostics are enabled, and is the first place to look when a notification went to the wrong place.
A summary of which source enabled each delivery is always archived as `delivery_provenance`.
