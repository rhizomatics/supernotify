---
tags:
  - transport
  - matrix
---
# Matrix Transport Adaptor

## Discovery

**Delivery (default selection).** The HA `matrix` integration has no config flow (YAML-only
setup), so SuperNotify can't detect it via a config entry — instead it checks directly whether
the `matrix.send_message` service is registered (which only happens once the bot has connected).
If found and no `matrix` delivery is defined, a `matrix` delivery is generated automatically. A
room ID/alias itself can't be auto-detected from a bare, unqualified value, but `matrix_room` is
a dedicated target category no other transport uses, so a target explicitly qualified with it
(`target: {matrix_room: "!room:server"}`) reaches this delivery automatically, the same way an
email address reaches the `email` delivery — no need to name `matrix` in `delivery:` or a
scenario. With nothing qualified as `matrix_room` given, the delivery is simply skipped.

## Motivation

Sends messages to [Matrix](https://matrix.org/) rooms through the Home Assistant
[`matrix`](https://www.home-assistant.io/integrations/matrix/) integration, calling the native
`matrix.send_message` service (not the thin legacy notify wrapper) for control over format,
images and threads.

## Features

* HTML or plain text format (`matrix_format`), defaulting to HTML when a title is present so the
  title can be rendered in bold.
* Threads (`matrix_thread_id`).
* Camera snapshot attachment via `grab_image()` (`matrix_attach_image: true`).
* Opt-in emoji prefix derived from the SuperNotify priority (Matrix has no native priority).
* Room target validation: the service rejects the whole call if any target is invalid, so targets
  are pre-filtered to room IDs (`!abc:server`) or aliases (`#name:server`).

## Configuration

```yaml
delivery:
  matrix_alerts:
    transport: matrix
    target:
      - "!roomid:matrix.org"
    data:
      matrix_priority_prefix: true
    inclusion: explicit
```

For snapshots the integration checks local paths with `is_allowed_path`, so the SuperNotify media
path must be listed in `homeassistant.allowlist_external_dirs`; otherwise the image is dropped by
the integration (the text message is still sent first).

## Matrix Data Keys

* `matrix_format` — `text` | `html` (default `html` with a title, `text` otherwise)
* `matrix_thread_id` — send into a Matrix thread
* `matrix_attach_image` — attach the camera snapshot (default `false`)
* `matrix_priority_prefix` — prefix with a priority emoji (default `false`)

## Notes

* The service `data` sub-dict is strict: only `format`, `images` and `thread_id` are accepted, so
  residual generic data keys are not forwarded (debug log).
* There is no title field: the title is composed into the body (bold + line break in HTML, plain
  line break in text).
* With `format: html` the core sets both `formatted_body` and the plain `body` to the same string,
  so clients without HTML support show raw tags — this mirrors core behaviour.
