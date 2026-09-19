# Roadmap

See also [Principles](./principles.md) for what guides development.

## Home Assistant Version Compatibility

When the following versions meet the 6-month ago window for testing, here are the changes to make

### 2026.2

Remove Py3.13 compatibility and testing

### 2026.8

Switch from `voluptuous` to `probatio`

## Features

### Packages

See [Packages](./packages.md)

### Extended UI Configuration

Second and further phases identified at [ConfigFlow](./configflow_approach.md)

## Internal Improvements

The internals of the code get more complex and harder to debug over time as functionality added, so continual need to go back over and force it to be simpler, while maintaining
all reasonable backward compatibility.

### Overhaul use of `data` in pipeline

`extra_data` (and the older nested `data` of `notify.supernotify`) is currently merged into the same `data` that carries delivery, target and scenario data, all the way to the transports. That has some side effects:

- Supernotify's own transports read their options from it, for example `matrix_format` or `chime_tune`, so it is not purely data for the underlying integration
- `priority`, `message_html`, `spoken_message`, `force_resend` and `timestamp` are taken out of it by the envelope, so a value meant for the target integration, such as a mobile app push's own `priority`, never reaches it
- some transports, such as email and the generic `ntfy` and `notify_events` handling, read `media` and `actions`
  from that data rather than from the notification's own, which needs checking against the top level `media`
  and `actions` used by `supernotify.notify`

The plan is for `extra_data` to be passed through untouched, with Supernotify's own transport options and fields kept apart from it. Generic `data` mapping other
than `extra_data` should terminate as soon as action handled.

Consider simplifying the `data` section needed for `delivery` definitions and overrides.

Overhaul the Envelope's use of pop and get to pick out data elements such as priority. For something like priority the order should be:

- Notification Level
  - Global defaults
  - Action Data
  - Scenarios
- Envelope Level
  - Target level overrides
  - Delivery Config level overrides
  - Delivery Action Data overrides

The `priority` on the action data would always win, _unless_ the action data also had a delivery override with a different priority. (Question - scenarios, deliveries etc should be able to override too, so does a delivery level config priority win over a notification level action priority? Probably should do so, and use delivery overrides in action to resolve that if the default behaviour doesn't suit)

### Per-delivery priority

Setting `priority` in a delivery, target or scenario `data` block changes the priority of just that delivery, for
example to downgrade one channel while the rest stay at the call's priority. It works, but is not documented,
and only affects what the transport sees. Delivery selection by priority, snoozing and scenario conditions
still use the priority of the original call.

The plan is to make this a documented, supported setting, and decide which of those should follow it.

## Completed Roadmap

- [ConfigFlow](./configflow_approach.md)
  - v2.0.0
  - Partially completed, basic YAML only
- [Deliveries and Transports](./deliveries_and_transports.md)
  - v2.5.0
