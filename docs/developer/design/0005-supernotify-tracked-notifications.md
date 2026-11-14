# RFC 0005: Live notifications in Supernotify

Created: 2026-10-07
Author: Jey Burrows
Status: draft
Revised 2026-10-12 after Appliance Auto Notify v0.7.0, [#254](https://github.com/rhizomatics/supernotify/issues/254) and [appliances_autonotify#4](https://github.com/rhizomatics/appliances_autonotify/issues/4)

## Summary

Supernotify should own the lifecycle of a live notification: one that is started, updated in place and ended. The main case is a Live Activity on iOS or a Live Update on Android. Persistent notifications are a secondary case, since they can also be replaced and dismissed, however in their case the state is managed by the Persistent Notification integration, whereas for Live notifications the state is owned by Supernotify, using Home Assistant mechanisms.

Today the caller has to build that lifecycle itself out of mobile push details, and Appliance Auto Notify got it wrong in a way that failed silently.

The proposal adds one `live:` mapping to `supernotify.notify`, a `mobile_live` transport beside `mobile_push`. With them:

- an ordinary notification becomes live by adding `live:` with an id,
- a later call can be as small as the id and a number,
- an `end` command sends the final content,
   - and the live item is then closed under a rule: at once, after a set time, or when someone clears it.
   - Live notifications always get cleaned up, even if the calling component is restarted or dies, or Supernotify restarts, or the mobuile phone goes out of range and back
 - Repeated %age updates can be skipped for archiving unless explicitly switched on

Supernotify keeps everything needed to update or close the live notification, so the caller does not repeat it. Supernotify also decides which deliveries can show one, which devices received the start, and in what order calls are handled.

Supernotify does not decide what is happening in the real world. For a gate left open or a doorbell, the automation or Autonotify component says when the event starts and ends, as it does for an appliance cycle.

After the change, Appliance Auto Notify passes message, title, the `live:` mapping, and targets or deliveries only if the user chose some. It makes no enquiries, names no transport and sends no Companion App keys.

## Terms

This RFC introduces, extends or refines the terms below. Once the names are agreed, documentation, configuration keys, code and log messages use them with these meanings and no others.

| Term                      | Status   | Meaning                                                                                                                                                  |
|---------------------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| Live notification         | New      | One ongoing thing reported over several `notify` calls: a cycle, an open gate, a delivery at the door.                                                   |
| Live item                 | New      | What one device shows for a live notification: a Live Activity on iOS, a Live Update or progress notification on Android, a card in the persistent list. |
| Live part                 | New      | The part of a `notify` call that opens, updates or closes live items. Described by `live:`.                                                              |
| Standard part             | New      | The part of a `notify` call that is an ordinary notification: spoken, chimed, e-mailed or pushed.                                                        |
| Live delivery             | New      | A delivery whose transport can show a live item.                                                                                                         |
| `mobile_live`             | New      | The transport for live items on phones. `mobile_push` keeps to standard notifications.                                                                   |                                       |
| Id                        | New      | The caller's name for a live notification, unique only within its source.                                                                                |
| Tag                       | Refined  | The identifier Supernotify gives transports, built from source and id. Was the caller's `mobile_push_notification_tag`.                                  |
| Record                    | New      | What Supernotify stores for a tag, so later calls need not repeat it.                                                                                    |
| Start, update, end, clear | New      | The four commands.                                                                                                                                       |
| End                       | New      | The caller saying the ongoing thing is over. The live item gets its final content. It does not by itself remove the item.                                |
| Finished                  | New      | The state of a live item after an end and before it is closed.                                                                                           |
| Close                     | New      | Supernotify removing a live item, whatever caused it.                                                                                                    |
| Close rule                | New      | When a finished live item is closed: at once, after a time, or when cleared.                                                                             |
| Clear                     | Refined  | A request to close now, from the caller's `clear` command or a person's *Clear* button. Was `mobile_push_clear_notification`.                            |
| Expiry                    | New      | The limit after which Supernotify closes a live item that nothing else has.                                                                              |
| Announce                  | New      | Whether a call alerts: sends the standard part, and lets the live item make a sound.                                                                     |
| Quiet update              | New      | An update that is not announced. The default.                                                                                                            |
| Action group              | Extended | Now either standard or live. A live action group is only ever shown on live items.                                                                       |
| Scenario                  | Refined  | Now either standard or live, see [Scenarios](#scenarios).                                                                                                |
| Programme | New  | A type of cycle, or phase within an appliance cycle, like pre-heat or rinse |
| Cycle | New |  An external event such as usage of an appliance. Event is overloaded term.|



## What the caller has to know today

As of v0.7.0, Appliance Auto Notify carries nine pieces of Supernotify or Companion App knowledge to show one Live Activity per appliance cycle. Each is a place it can drift from Supernotify, and one of them already has.

| What the caller does                                                                                                                                | Why it has to                                                                                                                                   | Where                |
|-----------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|----------------------|
| Finds the names of every mobile push delivery, from the delivery switch entities and two enquiry actions                                            | Quiet updates and the clear must go to phones only, and `notify` cannot select deliveries by transport                                          | `supernotify_api.py` |
| Sets `delivery_selection: fixed` on quiet updates and the clear                                                                                     | Otherwise scenarios add Alexa and chimes to a silent update                                                                                     | `watcher.py`         |
| Sets `force_resend: true` on updates, and on a start soon after the last one                                                                        | The duplicate check hashes the message without digits, so "20% complete" repeats "10% complete"                                                 | `watcher.py`         |
| Sends `mobile_push_notification_tag`, `live_update`, `progress`, `progress_max`, `chronometer`, `when`, `notification_icon`, `silent`, `alert_once` | These are Companion App keys, passed through `extra_data`                                                                                       | `watcher.py`         |
| Sends `channel`, `importance` and `sticky`                                                                                                          | On Android a Live Update is otherwise silent at the start, and removed by a tap                                                                 | `watcher.py`         |
| Sends `critical_text` only when there is no finish time                                                                                             | On Android it replaces the countdown in the status bar chip                                                                                     | `watcher.py`         |
| Sends `url` and `clickAction` on the start and every update                                                                                         | iOS reads one and Android the other, and iOS needs it on every update                                                                           | `watcher.py`         |
| Sends a separate clear with `mobile_push_clear_notification`, then the end notification as a second call                                            | Closing a Live Activity is not itself a notification, and the clear's message is discarded                                                      | `watcher.py`         |
| Holds a lock, and tracks whether a cycle is running                                                                                                 | Home Assistant drops the activity token on end, so a late `live_update` starts a new activity, and Supernotify has no record that a tag is open | `watcher.py`         |

The extra data also reaches deliveries it was not meant for. The archived Alexa envelope for "Oven started" carried the mobile push tag and `live_update`. That was harmless here, but it shows the keys are not scoped to a transport.

The field by field behaviour of both phone platforms is recorded in the Appliance Auto Notify [mobile platforms](https://github.com/rhizomatics/appliances_autonotify/blob/main/docs/mobile_platforms.md) page. This RFC refers to it as the platform notes.

## What went wrong in practice

Using v0.2.0 of Appliance Auto Notify, an oven cycle started and ended correctly, Alexa announced both, and the Live Activity stayed on the phone. The clear was never sent, and nothing was logged.

1. Delivery Control had default inclusion set to `explicit`.
2. That made the built-in `mobile_push` delivery non-implicit, so `enquire_implicit_deliveries` left it out.
3. It is not in the YAML `delivery:` section either, so `enquire_configuration` did not list it.
4. The caller found no mobile push delivery and skipped the clear, and every progress update before it.
5. The start had still reached five devices, because the `normal_day` scenario enabled `mobile_push`.

Supernotify's archive for that minute holds "Oven started" and "Oven is finished" and no clear between them. The caller now also reads the delivery switch entities, which fixes this case and adds a third thing it has to know.

Two more failures were found by reading the code, not seen live. Both are still possible in v0.7.0:

- **Reopened activity.** A progress update sent after the clear is treated by Home Assistant as a new start, because the token for that tag has gone.
- **Start and end reach different devices.** The start is selected by scenario and occupancy at that moment. The clear goes to every mobile push delivery later, under whatever applies then. A phone that got the start can miss the clear, and a phone that never got the start is sent one.


##  HA Compatibility
An action call such as below can be easily moved over to Supernotify.

```yaml
action:
  - action: notify.mobile_app_<your_device_id_here>
    data:
      title: "Washing Machine"
      message: "Cycle started"
      data:
        tag: washer_cycle
        live_update: true
```

##




## Proposal: the `live:` mapping

**Under Review - incorporating new work on source and other refinements**

A live notification is reported over several `notify` calls that share an id. Each call can carry two parts:

- the **standard part**, the ordinary notification that is spoken, chimed, e-mailed or pushed,
- the **live part**, which opens, updates or closes the live item on each device.

All existing `notify` fields keep their meaning and describe the standard part. The `live:` mapping describes the live part, and inherits `title` and `message` from the call unless it gives its own. There is no single `live_message` field, as there is a `spoken_message`, because the live part has more to say than one string.

If the upstream, e.g. AutoNotify, wants to have a non-live and notification together, it

```yaml
action: supernotify.notify
data:
  live:
     id: dw-1001
     command: start
     icon: dishwasher-outline
     finish_at: 2026-07-04T16:09:00.9949Z

```

### Fields

 inside `live:`

| Field                      | Type                                | Meaning                                                                                                                                               |
|----------------------------|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| `id`                       | string                              | Ties the calls together. Chosen by the caller, and only needs to be unique within its source. Or SN assigns one and hands it back in response                                                          |
| `command`                  | `start`, `update`, `end` or `clear` | Optional. Without it, a call opens the live notification if none is open for the id, and updates it otherwise. `end` and `clear` are always explicit. Phase change to be clarified |
| `announce`                 | boolean                             | Whether this call alerts. Defaults to true for `start` and `end`, false for `update`. Never applies to `clear`.                                       |
| `close`                    | `now`, `cleared` or a duration      | On `end`, the close rule. See [Ending and closing](#ending-and-closing).                                                                              |
| `title`, `message`         | string                              | Text for the live part, where it should differ from the standard part.                                                  Defaults to the main notification `data`fields                              |
| `progress`                 | 0 to 100                            | How far through, when the caller knows. A live item without it shows no bar.                                                                          |
| `finish_at`                | datetime                            | When it is expected to end, for a countdown.                                                                                                          |
| `icon`                     | icon name                           | Shown where a transport has room for one.                                                                                                             |
| `url`                      | path or URL                         | Where a tap goes.                                                                                                                                     |
| `channel`                  | string                              | Android notification channel. Its sound and importance are fixed when the phone first sees it, so the name should not change.                         |
| `actions`, `action_groups` | as on `notify`                      | Buttons for the live part only. See [Actions](#actions).                                                                                              |
| `data`                     | mapping                             | Any other Companion App key, passed to `mobile_live` only, for whatever this list does not cover.                                                     |

All names are placeholders.

Any field left out of an update keeps the value Supernotify last recorded. Fields with an unknown or unavailable value are left out, not sent as text.

### What each command does

| Command  | Live part                                                                                                                        | Standard part                                       |
|----------|----------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------|
| `start`  | Opened on every selected live delivery. Supernotify records which deliveries and targets accepted it.                            | Sent by normal selection, unless `announce: false`. |
| `update` | Updated in place on the recorded targets, quietly. Never falls back to another delivery, and is exempt from the duplicate check. | Not sent, unless `announce: true`.                  |
| `end`    | The final content is sent to the recorded targets, with no bar or countdown. The item is then closed under the close rule.       | Sent by normal selection, unless `announce: false`. |
| `clear`  | Closed now on the recorded targets.                                                                                              | Never sent.                                         |

A phone should not alert twice for one call. So a device that takes the live part of a call is not also sent the standard part of that call by `mobile_push`, and `announce` decides whether its live item makes a sound. Every other delivery, and every phone that cannot show a live item, gets the standard part as usual.

This covers the cases Appliance Auto Notify has today:

| Case                                                                      | Call                                                   |
|---------------------------------------------------------------------------|--------------------------------------------------------|
| Cycle starts                                                              | `start`                                                |
| Cycle starts with *Notify start* off                                      | `start` with `announce: false`                         |
| Progress, program or oven temperature changes                             | `update`                                               |
| Each 10% with *Notify progress* on                                        | `update` with `announce: true`                         |
| Oven up to heat                                                           | An ordinary `notify` with no `live:`, then an `update` |
| Cycle finishes                                                            | `end`                                                  |
| Cycle finishes, and the result should stay until the appliance is emptied | `end` with `close: cleared`, then `clear`              |
| Cycle aborted, or *Notify end* off                                        | `clear`                                                |

### Ending and closing

Ending and closing are separate steps. One live item lasts for the whole notification, and the last thing it shows is the result.

This follows Apple's guidance for Live Activities:

> Always include an updated `Activity.ContentState` to ensure the Live Activity shows the latest and final content update after it ends. This is important because the Live Activity can remain visible on the Lock Screen for some time after it ends.

An `end` always sends final content: the end message, with the bar and countdown removed. On a phone that final content is the end notification, and it alerts unless `announce: false`. The item is then finished, and is closed by its close rule:

| `close`                        | The finished item is closed                                                                                                                   |
|--------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| `now`                          | At once. The result is not left on screen, so phones get the standard part through `mobile_push` instead, as they do today.                   |
| a duration, such as `00:15:00` | After that time.                                                                                                                              |
| `cleared`                      | When a `clear` command arrives, or someone presses the standard live *Clear* button on any device. This is the "finished" being acknowledged. |

Whatever the rule, a `clear`, the *Clear* button, the user swiping the item away, and expiry all still close it. The default rule is set on the live delivery, so a caller only names one when its case differs.

While an item is finished, an `update` is still accepted. With `announce: true` that is a reminder. The *Emptied* and *Remind me* buttons in [appliances_autonotify#3](https://github.com/rhizomatics/appliances_autonotify/pull/3) need exactly this: *Emptied* is a `clear`, and each reminder is an announced `update`.

Home Assistant may not support all of this natively. The Companion App's `clear_notification` ends an activity at once and carries no final content, so Supernotify sends the final content as one more update and the clear later, on its own timer. If Home Assistant gains an end with final content and a dismissal time, only the `mobile_live` mapping changes. Callers do not.

### Identity and tag

The caller is not expected to choose an id that is unique across Home Assistant. Supernotify qualifies it by the source of the call, so two automations can both use `gate`.

- The tag sent to transports is derived from source and id alone. The same tag is used for every command and on every transport: the mobile push `tag` and the persistent `notification_id`.
- The tag has no timestamp, so it can still address a live notification that Supernotify has no record of.
- The time of the start is kept in the record, and tells one run of an id from the next in the archive.
- iOS refuses an activity whose tag has characters outside `[A-Za-z0-9_-]` or is over 64 characters, so Supernotify builds the tag to fit.

`source` is a top level field that any notification can carry. It cannot be required of ordinary notifications after the fact, so there it stays optional. A live notification is new, so there it is required from the start.

- **Automations and scripts** give none. Supernotify takes it from the Home Assistant context of the call, so an ordinary user has nothing extra to write.
- **Components and anything else** that calls `notify` directly set `source`, for example `appliance_autonotify`.
- A live call with no source, given or found, is refused with an error that says so.
- An ordinary notification with no source, given or found, is sent as now.


### What Supernotify takes on

- **A record per tag.** It holds everything needed to update or close the live notification: the deliveries and targets that accepted the start, the last title, message, icon, tap URL, channel, progress and finish time, the start time, the close rule with any time it is due, and an expiry. It survives a restart, because an appliance cycle can outlast one.
- **No record is not an error.** After a restart of the caller, or a start that was never sent, the tag still addresses whatever is on the phone.
    - An `update` creates the record it would have had from a start, using what the call carries, and updates the live deliveries from normal selection.
    - An `end` or `clear` closes the tag on those same deliveries, and does nothing where there is nothing to close.
    - Values only known at the start, such as the start time, may be missing from an end message. That is acceptable.
- **Ordering.** Calls for one tag are handled one at a time. A closed or cleared tag is remembered for a short while, and an `update` in that time is dropped, so a late update cannot reopen it. A finished item is not yet closed, so it accepts updates. A `start` always opens.
- **Live deliveries.** A new `TransportFeature` flag marks transports that can show a live item. `mobile_live` is the first, see below. Persistent notifications are the second, replacing by `notification_id` and dismissing on close.
- **Scoped data.** The Companion App keys are built inside `mobile_live`, so they never reach an Alexa or e-mail envelope. A close carries the tag and nothing else.
- **Throttling.** Quiet updates for one tag are held to a minimum interval, keeping the latest. Announced updates and ends are never held. The caller still decides which changes are worth sending.
- **Expiry.** A live item that nothing else has closed, finished ones included, is closed 8 hours after its last command, which is when iOS ends an activity anyway.
- **Saying what happened.** The `notify` response reports what each call opened, updated or closed. A live part with nowhere to go logs a warning.

### The `mobile_live` transport

Live items on phones get a transport of their own, beside `mobile_push`, with a built-in delivery as `mobile_push` has.

- **Each does one job.** `mobile_push` sends standard notifications and is unchanged. `mobile_live` sends only live parts, and is never selected for a call without `live:`.
- **Directed like any delivery.** It can be enabled, disabled, targeted, and chosen by scenario or delivery selection. A household can send live items to some phones and ordinary pushes to others, or make something live only.
- **Its own configuration.** The default close rule, the default Android channel, and the live action groups added to every live item are options of the delivery.
- **Only phones that can show one.** It skips a device that cannot show a live item, which then gets the standard part from `mobile_push`.
- **Shared code.** What both need, such as finding a person's devices and handling a device that has gone away, moves to a module both use.

The mapping to Companion App keys is settled from the platform notes. Supernotify applies it so the caller sends none of these.

| `live:`                        | Companion App keys                                                                     | Notes                                                                                                                        |
|--------------------------------|----------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| any                            | `tag`, `live_update: true`                                                             |                                                                                                                              |
| any                            | `sticky: true`, `importance: high`                                                     | Android only. Without them the start is silent and a tap removes the Live Update.                                            |
| `channel`                      | `channel`                                                                              | Android only. Defaults to the delivery's one channel for all live items.                                                     |
| `progress`                     | `progress`, `progress_max: 100`                                                        |                                                                                                                              |
| `finish_at`                    | `chronometer: true`, `when`                                                            |                                                                                                                              |
| `progress` without `finish_at` | `critical_text` as the percentage                                                      | The chip shows this in place of the countdown, so it is only sent when there is no countdown. Kept under about 7 characters. |
| `icon`                         | `notification_icon`                                                                    |                                                                                                                              |
| `url`                          | `url` and `clickAction`                                                                | Sent on every update, from the record.                                                                                       |
| a call that is not announced   | `silent: true`, `alert_once: true`                                                     | One for each platform.                                                                                                       |
| `end`                          | A last update with the end message and no `progress`, `chronometer` or `critical_text` | Whether it should stay a `live_update` is for the testing plan.                                                              |
| close                          | `message: clear_notification` with the `tag`                                           | From `clear`, the close rule or expiry.                                                                                      |

Phones that cannot show a Live Activity are not a problem on Android. Versions 7 to 15 show an ordinary notification with the bar and timer, replaced in place. iOS below 17.2 is not yet checked, see the [testing plan](#manual-testing-plan).

### Actions

Buttons that suit a standard push rarely suit a live notification, so the two are configured separately.

- Scenario and default `action_groups` apply to the standard part only. None are added to the live part.
- The live part gets only what `live.actions` and `live.action_groups` name, plus any live action group the live delivery is configured to add to every live item.
- With neither, a live notification has no buttons.
- Supernotify provides one standard live action group, to clear the live notification on every device and to snooze it. It can be added to every live item in the delivery's configuration, so callers do not repeat it.
- Clearing from a button fires an event with the Home Assistant context, so an automation can see who cleared it. This is the "one person has seen it" case in #254, without any notion of acknowledgement.

### Scenarios

Scenario conditions can use the source, live id and command, so a scenario can match all appliance activity without matching message text.

One call has two parts, so a scenario could otherwise apply twice, once to each. The proposal is that a scenario is either standard or live:

- a standard scenario, as now, affects only the standard part,
- a scenario marked live affects only the live part: which deliveries can show it, and which live action groups it gets.

This costs some extra YAML where both parts want the same rule, and keeps each scenario's effect predictable. With a separate `mobile_live` delivery, much of the choice of where live items go can be made on the delivery, with no scenario at all.

## What the caller sends, before and after

Today, the end of a cycle is two calls, after two enquiries and a scan of switch entities:

```yaml
# 1. close the Live Activity, on deliveries the caller looked up itself
action: supernotify.notify
data:
  message: Oven is finished   # discarded
  title: Oven
  delivery: [mobile_push]
  delivery_selection: fixed
  force_resend: true
  extra_data:
    mobile_push_notification_tag: appliance_01M4AHCN
    mobile_push_clear_notification: true
```
```yaml
# 2. tell everyone
action: supernotify.notify
data:
  message: Oven is finished
  title: Oven
```

Proposed, the whole cycle is:

<!-- docs-check: allow-keys live source -->

```yaml
action: supernotify.notify
data:
  message: Oven started
  title: Oven
  source: appliance_autonotify
  live:
    id: oven
    icon: mdi:stove
    channel: Appliances
    url: /dashboard-kitchen
```
```yaml
action: supernotify.notify
data:
  source: appliance_autonotify
  live:
    id: oven
    progress: 40
    finish_at: "2026-10-07T11:15:00+01:00"
    message: Hot air 180°C
```
```yaml
action: supernotify.notify
data:
  message: Oven is finished
  title: Oven
  source: appliance_autonotify
  live:
    id: oven
    command: end
```

An automation would leave out `source`. Targets and deliveries are added to any of these only when the user picked some.

What can then be deleted from Appliance Auto Notify: `deliveries_by_transport` and both enquiries, the `mobile_only` path, the `fixed` and `force_resend` settings, every Companion App key, the `mobile_push` transport name, and the send lock. It keeps deciding when a cycle starts and ends, what the appliance is doing, and which changes are worth an update.

### Other callers

The same commands cover the cases in #254. The automation supplies the event, and there is no progress bar.

| Event          | Start                                                     | End                                                                   |
|----------------|-----------------------------------------------------------|-----------------------------------------------------------------------|
| Gate left open | Gate opens                                                | Gate closes: `clear`                                                  |
| Water leak     | Sensor wet, with an announced `update` while it stays wet | Sensor dry: `end` with `close: cleared`, cleared by whoever checks it |
| Doorbell       | Ring                                                      | Door opened, or the standard live *Clear* button on any phone         |

## Smaller fixes worth making regardless

These stand on their own and would have prevented or exposed the oven failure without the larger change. All are still open as of 2026-10-12. The first two matter less now, since the caller reads the delivery switch entities instead.

- **An enquiry that lists every delivery.** No action returns all deliveries with their transport, inclusion and enabled state. `enquire_implicit_deliveries` and `enquire_configuration` together miss a built-in delivery that Delivery Control has made explicit.
- **Select deliveries by transport.** Let `notify` take a transport name where it takes delivery names, so a caller never needs the enquiry.
- **Duplicate check and counters.** Stripping digits before hashing treats a changing percentage as a repeat. A live update should be exempt. Whether ordinary messages that differ only by a number are duplicates is worth a second look.
- **Clear without a tag.** Mobile push logs a warning and carries on when `mobile_push_clear_notification` is set with no tag. The response should say the clear did nothing.
- **Clear with a full payload.** A clear is sent with the whole notification data, including action groups. It needs only the tag.

## Settled since the first draft

Answered by the Appliance Auto Notify work up to v0.7.0 and its platform notes, or decided in review.

- [x] **Android.** The same payload works on both platforms, with three Android additions: a channel with `importance: high`, `sticky`, and `critical_text` only without a finish time. They are in the [mapping](#the-mobile_live-transport).
- [x] **Click thru.** The caller gives a URL, Appliance Auto Notify from its *Dashboard to open* setting. Supernotify sends it on every update.
- [x] **Cycle name.** The title stays as it was at the start. The live message says what the appliance is doing, and the bar or the chip carries the number. The standard part has its own message, which is why `live:` can override `message`.
- [x] **Old phones.** Android 7 to 15 show an ordinary notification with a progress bar, updated in place and quiet. iOS below 17.2 remains to be checked.
- [x] **Update with no start on record.** Treated as a start that alerts nobody, see [What Supernotify takes on](#what-supernotify-takes-on).
- [x] **Expiry.** 8 hours after the last command. iOS ends an activity after 8 hours, and marks it stale 30 minutes after the last update when it has no timer.
- [x] **Where throttling lives.** Both. The caller sends what is worth showing, currently every 10%, then every 2% from 90%, and each 5° of oven temperature. That is about 18 pushes a cycle per phone, against a relay limit of 500 a day. Supernotify adds a minimum interval as a floor.
- [x] **Other transports.** Persistent notifications are in the first version. HTML5 and ntfy can follow.
- [x] **Callers without Supernotify.** Appliance Auto Notify falls back to `notify.send_message` for start and end only. That stays the caller's concern.
- [x] **Source.** A top level field for any notification, required for live ones, taken from the call context for automations and scripts, and given explicitly by components.
- [x] **End and close.** An end sends final content to the same live item, which is closed later under a close rule.


## Open questions

- [ ] **Naming.** The field names and the [terms](#terms): `live`, `id`, `source`, `command`, `close`, `announce` and `mobile_live`, or something closer to existing Supernotify vocabulary? `tag` is avoided as a field name because Home Assistant also uses it for scanned tags.
- [ ] **An id is required.** Could `live: true` be enough for an automation, with the id left out and the source alone as the tag? That allows one live notification per automation.
- [ ] **A separate transport.** `mobile_live` is expected to be easier to manage than `mobile_push` doing both jobs. A short spike should confirm how much code the two share.
- [ ] **One alert per phone.** Is skipping the `mobile_push` standard part for a device that took the live part the right default, and should a delivery be able to turn it off?
- [ ] **Which phones can show one.** Can `mobile_live` tell from the device registry, or does it need a list?
- [ ] **Default close rule.** What should the delivery's default be when none is configured? A short time, such as 15 minutes, keeps the result visible without leaving it for hours.
- [ ] **Who gets the end message.** Normal selection at the time of the end, as proposed, or the same recipients as the start?
- [ ] **Scenarios.** Is a scenario that is either standard or live acceptable, or should one scenario be able to affect both parts?
- [ ] **Minimum interval.** What value, and should it differ by platform? See the testing plan.
- [ ] **Expiry override.** Should a caller be able to set a shorter or longer limit than 8 hours? A finished item waiting to be cleared may want longer, and iOS removes an activity from the Lock Screen at 12 hours whatever is asked.
- [ ] **Buttons on iOS.** Whether a Live Activity can show action buttons at all is not known. If not, the standard live action group only helps Android and persistent notifications.
- [ ] **Many at once.** With power monitors discovered automatically, several live notifications may run together, most with no progress or finish time. Android shows one status bar chip, for the newest. Is a way to rank them needed?
- [ ] Separate handling, for watches, carplay, macbooks, including selectively enabling
- [ ] Occupancy, e.g. where phones don't have remote HA and not present, so can't get live activity handshake

## Manual testing plan

The appliance work raised questions that only a phone can answer. Each check below is recorded with the phone, OS and Companion App version, and the result goes into the platform notes.

### Setup

- One iPhone on iOS 17.2 or later with a Dynamic Island, and one Android 16 phone. An older phone of each kind if available.
- Both in one `mobile_push` delivery, plus a persistent delivery and one spoken delivery to show what leaks.
- Calls made by hand from Developer Tools, with the payloads Appliance Auto Notify sends today, so that the results hold before any of this RFC is built.
- After each call, compare the Supernotify archive with the Companion App's notification history on the phone, to tell a push that was never sent from one that never arrived.

### Checklist

Start and update:

- [ ] iOS: send a quiet update 1, 5 and 30 seconds after the start. Record whether it alerts. Core sends an update as another push-to-start until the app has reported the activity's own token, which would alert.
- [ ] iOS: does the start make a sound, or only show a banner?
- [ ] Both: send 20 quiet updates at 5 second intervals, then at 60 second intervals. Count how many reach the phone, to choose the minimum interval.
- [ ] Android: repeat with the screen off for 30 minutes. Record whether the bar falls behind, and whether FCM priority `high` fixes it.
- [ ] Both: send an update for a tag that was never started. Record whether it opens silently.
- [ ] Both: restart Home Assistant during an activity, then send an update and a clear. Record whether the same activity is updated and closed.
- [ ] iOS below 17.2: send a start and an update. Record what the phone shows, and whether each update alerts.

End:

- [ ] iOS: send a clear with no end notification after it. Record whether the phone alerts. The app source suggests the clear carries an alert with the title.
- [ ] Both: send a clear for a tag that is not on the phone. Confirm nothing is shown.
- [ ] Both: send an update 1 second after a clear. Record whether the activity reopens.
- [ ] Android, One UI: end two Live Updates 2 seconds apart, three times. Record whether the second stays on screen, and the *Active notification count* sensor's tags if it does.
- [ ] Android, One UI: repeat with 30 seconds between the two, to see whether spacing the clears avoids it.
- [ ] iOS: leave an activity with no end for 12 hours. Record when it goes stale and when it is removed.

Finished but not closed:

- [ ] Both: send a last update with the end message and no progress or timer, alerting. Record what the item looks like, and whether it alerts once.
- [ ] Android: send that last update with and without `live_update`. Record whether the item stays promoted, keeps the status bar chip, and can be swiped away.
- [ ] iOS: leave the finished activity alone. Record when it is marked stale, what stale looks like, and when it disappears.
- [ ] Both: send an alerting update to the finished item an hour later, as a reminder. Record whether it alerts and stays one item.
- [ ] Both: swipe the finished item away, then send a reminder. Record whether it comes back.
- [ ] Both: clear it, and confirm it goes from the Lock Screen, shade, chip and Dynamic Island.
- [ ] By reading Core and the Companion App source: can an activity be ended with final content, and with a dismissal time, as ActivityKit allows? Record what would need adding.
- [ ] Both: send a start as a live item and as an ordinary push to the same phone. Record whether it alerts twice, to confirm the one alert per phone rule is needed.

Actions and taps:

- [ ] iOS: send a Live Activity with two actions. Record whether any button shows, on the Lock Screen and in the Dynamic Island.
- [ ] Android: send a Live Update with two actions while a scenario with action groups is enabled. Record which buttons show and in what order.
- [ ] Both: tap the live notification with a URL set on the start only, then with it on every update.

Several at once:

- [ ] Both: run three activities together, one with a finish time, one with progress only and one with neither. Record which takes the status bar chip or the Dynamic Island.
- [ ] Both: end the newest. Record which takes its place.

Persistent notifications:

- [ ] Send two persistent notifications with the same `notification_id`. Confirm the second replaces the first.
- [ ] Dismiss by that id, then dismiss again. Confirm the second dismiss is harmless.

## Appendices
### Enriched Source

Several limitations with current Home Assistant

- The calling object - typically an automation or script - *is* available, but it is unwieldy to find, requiring either a scan of all states, or direct SQL queries
  - The calling object itself may have metadata - categories, labels - that are of value in conditions, or tracking
  - Note the `run_id` and automation source now tracked in Supernotify, sourced from trace helper
- For notification use cases, often the real context is the entity, device etc that led to the automation
  - Examples
    - A camera entity ID, or a Frigate event ID
    - A HomeConnect-enabled dishwasher, or a power monitor connected to a washing machine
  - The static metadata for this object may be needed, along with state, state attributes, state transition, event, and the new HA triggers
- Supernotify may need a clean way of discovering or accepting this info from AutoNotify components, or any other upstream that chooses to use them
- Some of this may eventually be part of HA, so doing it once within the code useful, to minimize migration path within code and for automations
- Condition code may need some shortcuts, like 'furthest back known context' that picks either parent or current context depending on availability
- May be multiple objects for same thing, e.g. onvif camera plus hikvision camera plus mpeg camera plus frigate camera plus SN camera config object
- AutoArm currently does this by passing an `apply_scenarios` however this is very limited for cases where multiple vars involved
  - Subject -> verb -> Object -> Medium -- sunrise disarmed alarm panel state reported by autoarm


Step back to *why* this is needed, or if it is really needed at all:

- Condition variables for scenarios, or conditional deliveries
  - Use cases needed
- Debugging, live or reading an archive notification to see why something happened
  - Archive notification is a more relaxed environment to do slow calls to pull in context
  - A method that turns existing HA context into useful user and automation refs is obvious, and orthogonal to this delivery
  - The full context doesn't have to be in Supernotify, HA already has a trace mechanism for working out what led to a state change or action call, and so long the info available upstream, its not needed in Supernotify only for debug
- Entities and attributes only required in Home Assistant for fine tuning notification delivery, all the interpretation of what is actually happening in the real world belongs in an Autonotify component or other upstream client


### Summary of Enriched Source

- Debugging
  - Improve the autonotify->supernotify traceability
    - trace is not available in archive JSON when Autonotify calls Supernotify at present
  - Improve the human readability of existing context - to an actual user ID and/or event, state change etc
  - Linkage where possible to a logbook view like Activity
- Conditionals
  - Speculative at present, no current use cases
- Other Purposes
  - Speculative at present, no current use cases
  - Treat existing context linkage method in `hass_api`with caution

`source` is not an immediate need.
## References

- [Auto Notify](./0003-auto_notifier.md) - The Auto Notify design doc
- [Auto Notify Support](./0003a-auto_notifier_support.md) - Appendix of changes anticipated before first real use, largely superseded.
- [Household Appliances Auto Notifier](./0004-household_appliances_auto_notifier.md) - The first caller
- [Mobile platforms](https://github.com/rhizomatics/appliances_autonotify/blob/main/docs/mobile_platforms.md) - Android and iOS behaviour, field by field, from Appliance Auto Notify
- [Supernotify #254](https://github.com/rhizomatics/supernotify/issues/254) - Ending a notification everywhere it was shown
- [Appliance Auto Notify #4](https://github.com/rhizomatics/appliances_autonotify/issues/4) - Results from real cycles on Android
- [Live Activities and Live Updates](https://companion.home-assistant.io/docs/notifications/live-activities)
- [iOS Live Activities UX Guidelines](https://developer.apple.com/design/human-interface-guidelines/live-activities)
- [iOS Live Activities API](https://developer.apple.com/documentation/activitykit)
