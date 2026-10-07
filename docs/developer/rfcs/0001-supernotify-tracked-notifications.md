# RFC 0001: Tracked notifications in Supernotify

2026-10-07 · Jey Burrows · Status: draft

## Summary

Supernotify should own the lifecycle of a notification that is started, updated and ended, so a caller only says which phase it is in. Today the caller has to build that lifecycle itself out of mobile push details, and Appliance Auto Notifier got it wrong in a way that failed silently.

The proposal adds three things to `supernotify.notify`:

- an id that ties the calls of one activity together,
- a phase
- optional progress.

Supernotify then decides which deliveries can show an update, which devices received the start, how to close it, and in what order.

After the change, Appliance Auto Notifier passes message, title, the tracking fields, and targets or deliveries only if the user chose some. It makes no enquiries, names no transport and sends no `mobile_push_*` keys.

## What the caller has to know today

Appliance Auto Notifier carries seven pieces of Supernotify or Companion App knowledge to show one Live Activity per appliance cycle. Each is a place it can drift from Supernotify, and one of them already has.

| What the caller does                                                                                                                                | Why it has to                                                                                             | Where                |
|-----------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|----------------------|
| Finds the names of every mobile push delivery, from two enquiry actions and the delivery switch entities                                            | Progress updates and the clear must go to phones only, and `notify` cannot select deliveries by transport | `supernotify_api.py` |
| Sets `delivery_selection: fixed` on updates and the clear                                                                                           | Otherwise scenarios add Alexa and chimes to a silent update                                               | `watcher.py`         |
| Sets `force_resend: true` on updates                                                                                                                | The duplicate check hashes the message without digits, so "20% complete" repeats "10% complete"           | `watcher.py`         |
| Sends `mobile_push_notification_tag`, `live_update`, `progress`, `progress_max`, `chronometer`, `when`, `notification_icon`, `silent`, `alert_once` | These are Companion App keys, passed through `extra_data`                                                 | `watcher.py`         |
| Sends a separate clear with `mobile_push_clear_notification`, then the end notification as a second call                                            | Closing a Live Activity is not itself a notification, and the clear's message is discarded                | `watcher.py`         |
| Holds a lock so an update cannot follow the clear                                                                                                   | Home Assistant drops the activity token on end, so a late `live_update` starts a new activity             | `watcher.py`         |
| Tracks whether a cycle is running, to skip updates outside one                                                                                      | Supernotify has no record that a tag is open                                                              | `watcher.py`         |

The extra data also reaches deliveries it was not meant for. The archived Alexa envelope for "Oven started" carried the mobile push tag and `live_update`. That was harmless here, but it shows the keys are not scoped to a transport.

## What went wrong in practice

Using v0.2.0 of Appliance Auto Notifier, an oven cycle started and ended correctly, Alexa announced both, and the Live Activity stayed on the phone. The clear was never sent, and nothing was logged.

1. Delivery Control had default inclusion set to `explicit`.
2. That made the built-in `mobile_push` delivery non-implicit, so `enquire_implicit_deliveries` left it out.
3. It is not in the YAML `delivery:` section either, so `enquire_configuration` did not list it.
4. The caller found no mobile push delivery and skipped the clear, and every progress update before it.
5. The start had still reached five devices, because the `normal_day` scenario enabled `mobile_push`.

Supernotify's archive for that minute holds "Oven started" and "Oven is finished" and no clear between them. The caller now also reads the delivery switch entities, which fixes this case and adds a third thing it has to know.

Two more failures were found by reading the code, not seen live:

- **Reopened activity.** A progress update sent after the clear is treated by Home Assistant as a new start, because the token for that tag has gone.
- **Start and end reach different devices.** The start is selected by scenario and occupancy at that moment. The clear goes to every mobile push delivery later, under whatever applies then. A phone that got the start can miss the clear, and a phone that never got the start is sent one.

## Proposal: tracked notifications

A tracked notification is one activity reported over several `notify` calls that share an id. Supernotify keeps a record per id and maps each phase onto whatever each transport can do.

### New fields on `supernotify.notify`

| Field         | Type                                 | Meaning                                                                             |
|---------------|--------------------------------------|-------------------------------------------------------------------------------------|
| `tracking_id` | string                               | Ties the calls of one activity together. Chosen by the caller, unique per activity. |
| `phase`       | `start`, `update`, `end` or `cancel` | Where the activity is. Absent means an ordinary notification, as now.               |
| `progress`    | 0 to 100, optional                   | How far through, when the caller knows.                                             |
| `finish_at`   | datetime, optional                   | When it is expected to end, for a countdown.                                        |
| `icon`        | icon name, optional                  | Shown where a transport has room for one.                                           |

The names are placeholders. All existing fields keep their meaning, so a caller can still pass `target`, `delivery` or `priority`.

### What each phase does

| Phase    | Deliveries used                                                              | Behaviour                                                                                                                                                        |
|----------|------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `start`  | Normal selection: scenarios, recipients, and any targets or deliveries given | Delivered as an ordinary notification. Transports that support tracking also open an ongoing item. Supernotify records which deliveries and targets accepted it. |
| `update` | Only the recorded targets on transports that support tracking                | Updates the ongoing item in place, silently. Never spoken, never chimed, no fallback, exempt from the duplicate check.                                           |
| `end`    | Recorded targets to close, then normal selection for the message             | Closes the ongoing item, then delivers the message as an ordinary notification. One call.                                                                        |
| `cancel` | Recorded targets only                                                        | Closes the ongoing item and says nothing.                                                                                                                        |

### What Supernotify takes on

- **A record per tracking id.** It holds the deliveries and targets that received the start, the last phase, and an expiry. It survives a restart, because an appliance cycle can outlast one.
- **Ordering.** Calls for one id are handled one at a time. An `update` that arrives after `end` or `cancel` is dropped.
- **A transport capability.** A new `TransportFeature` flag marks transports that can update in place. Mobile push is the first, and maps the phases to `tag`, `live_update`, `progress`, `chronometer`, `when` and `clear_notification`.
- **Scoped data.** The Companion App keys are built inside the mobile push transport, so they never reach an Alexa or e-mail envelope.
- **Saying what happened.** The `notify` response reports what each phase opened, updated or closed. A tracked phase with nowhere to go logs a warning.

## What the caller sends, before and after

A cycle that ends normally takes one call fewer, and each call says only what the appliance is doing.

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

```yaml
action: supernotify.notify
data:
  message: Oven started
  title: Oven
  tracking_id: appliance_01M4AHCN
  phase: start,
  icon: mdi:stove
```
```yaml
action: supernotify.notify
data:
  message: 40% complete
  title: Oven
  tracking_id: appliance_01M4AHCN
  phase: update
  progress: 40
  finish_at: "2026-10-07T11:15:00+01:00"
```
```yaml
action: supernotify.notify
data:
  message: Oven is finished
  title: Oven
  tracking_id: appliance_01M4AHCN
  phase: end
```

An aborted cycle sends `phase: cancel` with no message. Targets and deliveries are added to any of these only when the user picked some.

What can then be deleted from Appliance Auto Notifier: `deliveries_by_transport` and both enquiries, the `mobile_only` path, the `fixed` and `force_resend` settings, every `mobile_push_*` key, and the send lock. It keeps deciding when a cycle starts and ends, and stepping progress to every 10%.

## Smaller fixes worth making regardless

These four stand on their own and would have prevented or exposed the oven failure without the larger change.

- **An enquiry that lists every delivery.** No action returns all deliveries with their transport, inclusion and enabled state. `enquire_implicit_deliveries` and `enquire_configuration` together miss a built-in delivery that Delivery Control has made explicit.
- **Select deliveries by transport.** Let `notify` take a transport name where it takes delivery names, so a caller never needs the enquiry.
- **Duplicate check and counters.** Stripping digits before hashing treats a changing percentage as a repeat. A tracked update should be exempt. Whether untracked messages that differ only by a number are duplicates is worth a second look.
- **Clear without a tag.** Mobile push logs a warning and carries on when `mobile_push_clear_notification` is set with no tag. The response should say the clear did nothing.

## Open questions

- [ ] **Update with no start on record.** Drop it, or treat it as a start? Dropping is safer after a restart that lost the record. Treating it as a start recovers a missed one.
- [ ] **Who gets the end message.** Normal selection at the time of the end, as proposed, or the same recipients as the start?
- [ ] **Where throttling lives.** The caller steps progress to every 10% because phones throttle frequent updates. Should Supernotify enforce a minimum interval per tracking id instead?
- [ ] **Expiry.** What ends a record that never gets an `end`? A fixed limit, or a caller-supplied one? What the phone does with an activity that is never ended needs checking.
- [ ] **Other transports.** Persistent notifications, HTML5 and ntfy can each replace or dismiss an earlier message. Are any worth supporting in the first version?
- [ ] **Android.** The Companion App keys used here are shared, but only the iOS path was exercised. Does the same mapping hold?
- [ ] **Callers without Supernotify.** Appliance Auto Notifier falls back to `notify.send_message` for start and end only. That stays the caller's concern, unless there is a reason to change it.
- [ ] **Naming.** `tracking_id` and `phase`, or something closer to existing Supernotify vocabulary?
- [ ] **Click Thru** - What should happen if user clicks on the activity bar? Presently it just opens Home Assistant
- [ ] **Cycle Name** - The examples on HA Companion App site always have the appliance name as title, the phase as critical_text and f'{phase} in progress' as the message. These won't line up with what makes a good non-activity bar notification, which is further case for Supernotify managing the bars
- [ ] **Old Phones** - Older phones in the house won't get activity bar and may get annoying behaviour instead, or maybe only some people get some live activities

## References
- [Auto Notifier](./auto_notifier.md) - The Auto Notifier design doc
- [Auto Notifier Support](./auto_notifier_support.md) - Speculative version of this RFC prior to first real use
- [Live Activities and Live Updates](https://companion.home-assistant.io/docs/notifications/live-activities)
