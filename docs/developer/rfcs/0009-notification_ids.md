# RFC 0009: Notification IDs and Linking to Home Assistant

Created: 2026-10-17
Author: Jey Burrows
Status: draft

## Summary

Each notification has an id, a uuid1, used for its archive file, its media files and the logbook event. It does that job, but people can't use it. It's too long to read out or type, it looks like noise, and nothing in Home Assistant's Activity or History views refers to it.

This RFC sets out what the id should do. It should let a person get from a row in the Activity or History view to the archived notification, and from the archive back to the automation run, logbook and history that go with it. It compares the ways of doing that and proposes separating the id people use from the id the code uses, because the two have different constraints.

## Goals

- From a row in the Activity (logbook) view, or the History view, find the archived notification it belongs to
- From an archived notification, get to the automation or script run that sent it, and the logbook and history around it
- Keep the full JSON out of the Home Assistant database. The recorder only gets small events and entity states
- Work on an install where nobody has configured anything: no extra integrations, settings or YAML
- Give people a reference short enough to read out, type, or quote in an issue, such as "17 Oct #7"
- Keep the technical id unique, never reused, sortable by time, and safe in filenames and MQTT topics

## Current State

| Where | What it holds now |
| ----- | ----------------- |
| `Notification.id` | `str(uuid.uuid1())`, e.g. `642c73fc-ca23-11f1-97c3-a203a37618e8` |
| Archive file | `<local time to the minute>_<id>.json`, e.g. `2026-10-17T13-07_642c73fc-….json`. `_filename_period()` parses the first 16 characters to skip files outside a time range |
| MQTT archive | `<topic>/<same base filename>` |
| Media | `<id>.<ext>` and `<id>_<key>.<ext>` |
| Email | `Envelope.id` (`<notification id>_<delivery>`) as the `idstring` of `make_msgid()`, which adds its own time, random part and domain |
| Logbook | `supernotify_notification` event with `notification_id`, a 100 character summary, outcome and delivery names, fired with the notification's context |
| Recipient notify entities | `notify.recipient_<name>` state is set once per notification for each recipient reached, with the notification's context, so each delivery to a person is in the History and Activity views |
| Archive linkage | `original_context` (context `id`, `parent_id`, `user_id`, and the resolved `user`). From v2.15.1, `original_trace` (trace `key` and `run_id`) |
| Lookup | `ArchiveDirectory.read_entry()` returns the first file whose name *contains* the given string, used by the archive enquiry action |

## What Home Assistant Allows

Checked against HA 2026.10.1 and 2026.10.2, its frontend, and a test container.

### Activity view

- A logbook entry has only `name`, `message`, `entity_id`, `icon`, `domain`, `source`, `state`, `when` and the `context_*` fields. There's no URL field
- The message is plain text. The frontend swaps the first word that is an entity id for that entity's friendly name, but doesn't make it a link
- A row is linked through its context: "triggered by automation X" opens that automation's trace, and an entry with an `entity_id` opens that entity's more-info dialog
- The URL `/logbook?entity_id=…&start_date=…&end_date=…` filters by entity and time only. The `logbook/get_events` websocket command also takes a `context_id`

So a row can't link to one particular notification. It can show a reference as text, and it already shares a context with the archive entry.

### History view

- `/history?entity_id=…&start_date=…&end_date=…` shows the state of entities over a time range
- Each delivery to a recipient is a state change of their `notify.recipient_<name>` entity, with the notification's context

### Traces

- While an automation or script runs, `homeassistant.helpers.trace.trace_id_get()` returns `("<domain>.<config id>", run_id)`. The context var reaches the `supernotify.notify` and `notify.supernotify` handlers
- It's set on every install, since `automation` and `script` both depend on `trace`
- It's missing for calls from the developer tools, the REST API, Assist, or another integration's own task
- An automation without an `id` gets `automation.None` and no stored trace
- Only the last 5 runs of each automation or script are kept, by default
- Context vars are copied into tasks and event listeners, and HA never resets the trace id when a run ends. An integration reacting to an event an automation fired inherits that automation's trace id
- `trace/get` returns the run's `context`, which can be checked against `original_context`. `trace/list` doesn't include it. `hass.data[DATA_TRACE]` is internal, and its layout changed between 2026.10.1 and 2026.10.2
- One automation run can send several notifications. On the test container, two `supernotify.notify` calls in one run were archived with the same `run_id` and the same context id

### Linking keys

The context id is already the key shared by the logbook event, the recipient entity state changes, the automation trace and the archive entry. It links one run to many notifications, not to just one, but it's the one key that every view already has.

## Options for the Technical Id

| Option | Unique | Sortable | Human friendly | Notes |
| ------ | ------ | -------- | -------------- | ----- |
| A. Keep uuid1 | Yes | No | No | No change. Its first 8 characters are the low bits of the time, which repeat about every 7 minutes, so a short prefix isn't a safe reference |
| B. Local timestamp to the second + in-memory counter, e.g. `2026-10-17T13-07-57_3` | Yes, if the counter never resets while running | Yes | Partly | A restart can't happen within one second. The hour repeated when the clocks go back only clashes if the second and the count both repeat |
| C. Timestamp + persisted counter that never resets | Yes | Yes | No, eventually | At 500 a day, the counter passes 100,000 in under a year |
| D. Timestamp + persisted daily counter | Yes, with the timestamp | Yes | Yes, as date + number | Needs a `Store` file. A crash or backup restore can reuse a number on the same day |
| E. Trace `run_id` | No | No | No | Shared by every notification in a run, missing for calls from outside an automation or script, and 32 hex characters. Useful for linking, already kept as `original_trace` |
| F. HA context id (a ULID) | No | Yes | No | Shared by every notification in a run, like the `run_id`. Useful for linking, already kept as `original_context` |
| G. ULID (`homeassistant.util.ulid`) or `uuid.uuid7()` | Yes | Yes | No | Standard, time-ordered and unique without any state. A ULID matches HA's own context ids. Python 3.14, which Supernotify requires, has `uuid7()` |

E and F are good keys for linking, but they can't identify one notification. B, C and D try to make one value do two jobs, which is where their weaknesses come from.

## Proposal: Separate the Human Reference from the Technical Id

The two have different constraints:

| | Technical id | Human reference |
| - | ------------ | --------------- |
| Used by | Filenames, MQTT topics, media, events, code | People reading the Activity view, a notification, an issue or the archive viewer |
| Must be | Unique, never reused, safe in filenames | Short, easy to read out and type |
| Unique within | Everything, forever | One day, and only in practice |
| Survives a crash or restore | Yes, with no stored state | A rare repeat is acceptable |
| Format can change | Rarely, it ends up in stored files | Freely, it's only for display |

### Technical id

Option G: a ULID or uuid7. It's unique without stored state, sorts by time, and needs no counter. A ULID is the same kind of id as HA's context ids, so both read alike in the archive. Archive filenames keep the local time prefix, so `_filename_period()` and file listings are unchanged.

Option A, keeping uuid1, is also acceptable. Once the human reference is separate, the main reason left to change the technical id is sorting.

### Human reference

Option D's daily counter, used only as the reference: `ref: 7`, shown with the date as "17 Oct #7".

- Kept in a `Store` file, e.g. `.storage/supernotify.sequence` holding `{"date": "2026-10-17", "count": 7}`. The first notification after local midnight starts again at 1
- Taken when the notification is created, for every notification, whether delivered, suppressed, failed or a duplicate, so every archived notification has one
- A dry run (`dry_run: simulate`) takes a number from its own daily count instead, with a marker that can't be mistaken for a real one, e.g. `#D3`. The real numbering has no gaps, and a dry run's reference in its response, the logs or an AI agent's reply is plainly not a notification that was sent. Dry runs aren't archived or logged in the Activity view, so this count doesn't need to survive a restart
- Saved with `async_delay_save()` on a short delay. `Store` already does a final write when HA stops, so only a hard crash within the delay can reuse a number. Restoring a backup can too. Neither breaks anything, because the technical id stays unique
- The store file is removed when the config entry is removed (`async_remove_entry`)
- The existing notifications sensor isn't used. It only counts delivered notifications, and as an entity it can be disabled or deleted

Where the reference appears:

- In the archive, as `ref`, next to `id`
- In the logbook message, e.g. `sent 'Oven started' via alexa, mobile_push #7`. The row's own date makes it unique
- In the logbook event data, next to `notification_id`, so the archive viewer can find the entry from an event
- Optionally in the notification itself, such as an email footer, so a recipient can quote it

### Lookup

`read_entry()` changes from "the first file whose name contains this string" to exact matches:

- The full technical id
- A date and reference, e.g. `2026-10-17 #7`. Only that day's files are opened, using the time in their names
- An old uuid1 id, as now

### Linking

| From | To | How |
| ---- | -- | --- |
| Activity row | Archive | The `#7` in the message with the row's date. The archive viewer could also look up by context id |
| History (recipient entity) | Archive | The state change's context id, or its time |
| Archive | Automation trace | `original_trace`, as `/config/automation/trace/<id>?run_id=<run_id>`. The viewer checks the trace's context with `trace/get` before showing it as the sender |
| Archive | Activity | `/logbook?start_date=…&end_date=…` around the notification, narrowed to the sender entity when known. The viewer can list related entries itself with `logbook/get_events` and `context_id` |
| Archive | History | `/history?entity_id=notify.recipient_…&start_date=…` for the recipients reached |

The archive viewer itself, a bundled panel, is on the [roadmap](../roadmap.md#archive-viewer-and-logbook-linkage). The human reference and the exact lookup are useful without it, through the archive enquiry action.

## Compatibility

- Archive files already written keep their names and stay readable. `read_entry()` still finds them by uuid1
- Anything outside Supernotify that stores or parses `notification_id` sees a new format if the technical id changes. Supernotify Cards is the one to check
- `Envelope`'s own uuid1, used only when there's no notification, as in scenario tests, can stay

## Open Questions

- [ ] **ULID or uuid7?** A ULID matches HA's context ids and is shorter (26 characters against 36). `uuid7()` is in the standard library and is still a uuid
- [ ] **Change the technical id at all?** With a separate reference, uuid1 still works. Sorting by time is the main gain
- [ ] **Reference in the filename?** `2026-10-17T13-07_7_<id>.json` would let a lookup by reference skip opening files, at the cost of a longer name
- [ ] **Reference format.** `#7` alone, or with a date prefix where there's no date beside it, e.g. `1017-7`?
- [x] **Count dry runs?** Yes, from their own count with a marker, e.g. `#D3`, so the real numbering has no gaps
- [ ] **Dry run marker.** A `D` prefix, or a suffix such as `#3-dry`? It has to read clearly in the dry run response and in an AI agent's reply
- [ ] **Look up by context id.** A context id can match several notifications, so the lookup returns a list. Is that worth adding to the archive enquiry action before the viewer exists?

## Testing

- The reference survives a restart on the same day, and starts at 1 on the next local day
- Every archived notification has a `ref`, whatever its outcome
- A dry run gets a marked reference from its own count, and doesn't move the real count on
- Lookup by full id, by date and reference, and by an old uuid1 id. A partial number doesn't match a longer one
- The logbook message and event data include the reference
- Two notifications from one automation run get different ids and references, and the same `original_trace` and `original_context`
