---
tags:
  - transport
  - matrix
---
# Matrix Transport Adaptor

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
    selection: explicit
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
