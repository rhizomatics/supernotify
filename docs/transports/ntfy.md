---
tags:
  - transport
  - ntfy
---
# ntfy Transport Adaptor

## Motivation

ntfy became an official Home Assistant integration in version 2025.5. It provides
a privacy-first, self-hostable push notification service with a rich action API:
priority levels, action buttons, scheduled delivery, image attachments, and
message update/cancellation via `sequence_id`.

The existing `generic` transport can call `ntfy.publish`, but it cannot:
- map SuperNotify's 5-level priority to ntfy's integer scale (1–5)
- validate action button payloads before sending
- attach camera snapshots via HA's `camera.snapshot` service
- apply `boolify()` for YAML boolean strings

## Data keys

All keys are optional unless noted. Keys with prefix `ntfy_` are extracted
by the transport and never forwarded to `ntfy.publish`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ntfy_device_id` | `str` | — | **Required.** `device_id` of the ntfy topic configured in HA |
| `ntfy_priority` | `int` 1–5 | from SN mapping | Override priority (5=urgent, 1=min) |
| `ntfy_tags` | `list[str]` | `[]` | ntfy emoji shortcodes e.g. `["warning", "house"]` |
| `ntfy_click` | `str` (URL) | — | URL opened when notification is tapped |
| `ntfy_attach_image` | `bool` | `false` | Attach camera snapshot (requires `media.camera_entity_id`) |
| `ntfy_filename` | `str` | `snapshot.jpg` | Filename for the attachment |
| `ntfy_icon` | `str` (URL) | — | JPEG/PNG icon URL |
| `ntfy_markdown` | `bool` | `false` | Enable Markdown rendering in message body |
| `ntfy_delay` | `str` | — | Scheduled delivery: `"10m"`, `"1h30m"`, `"HH:MM"` |
| `ntfy_sequence_id` | `str` | — | Message ID for subsequent update/cancellation |
| `ntfy_email` | `str` | — | Email forwarding address |
| `ntfy_actions` | `list[dict]` | `[]` | Action buttons, max 3 (types: view/http/broadcast/copy) |

---

## Testing

Tested on Home Assistant 2026.3.4 with the ntfy official integration connected
to a self-hosted ntfy instance (ntfy v2.x).

**Functional tests performed:**
- [x] Base delivery: message and title appear correctly in ntfy app
- [x] Priority mapping: `critical` triggers urgent priority (bypasses DND)
- [x] Priority mapping: `minimum` delivers silently with no vibration
- [x] `ntfy_tags`: emoji tags visible in notification
- [x] `ntfy_click`: tap opens correct URL
- [x] `ntfy_attach_image: true` + `camera.ezviz_ingresso` → snapshot attached
- [x] `ntfy_actions` with 3 buttons: `view`, `http` (webhook), `http` (snooze)
- [x] `ntfy_delay: "30m"` — notification delivered after 30 minutes
- [x] `ntfy_sequence_id` — second call with same ID updates the notification
- [x] `ntfy_device_id` missing → `return False` with warning in log
- [x] `ntfy_actions` with malformed entry → entry skipped, valid ones delivered
- [x] YAML boolean strings `"true"` / `"false"` for `ntfy_attach_image`, `ntfy_markdown` — `boolify()` handles correctly
- [x] `ntfy_priority: 99` out of range → fallback to automatic mapping, warning logged

**Example configuration:**

```yaml
# delivery.yaml — minimal
ntfy_home:
  transport: ntfy
  selection: default
  data:
    ntfy_device_id: "abc123def456"
    ntfy_click: "http://homeassistant.local:8123"

# delivery.yaml — security channel with camera snapshot
ntfy_security:
  transport: ntfy
  selection: default
  data:
    ntfy_device_id: "abc123def456"
    ntfy_attach_image: true
    ntfy_click: "http://homeassistant.local:8123/lovelace/sicurezza"
    ntfy_tags:
      - house
      - rotating_light

# delivery.yaml — alarm channel with action buttons
ntfy_alarms:
  transport: ntfy
  selection: scenario
  data:
    ntfy_device_id: "abc123def456"
    ntfy_tags: [rotating_light, sos]
    ntfy_attach_image: true
    ntfy_actions:
      - action: view
        label: "Open dashboard"
        url: "http://homeassistant.local:8123/lovelace/allarmi"
        clear: true
      - action: http
        label: "✅ Acknowledge"
        url: "http://homeassistant.local:8123/api/webhook/ack_alarm"
        method: POST
        clear: true
```

**Example call:**

```yaml
action: supernotify.notify
data:
  message: "Motion detected at entrance"
  title: "📷 Front Camera"
  data:
    media:
      camera_entity_id: camera.ezviz_ingresso
```

**Expected behavior:**
- ntfy app receives push with title, message, attached snapshot, and action buttons
- Tapping "Open dashboard" navigates to the HA security Lovelace view
- Tapping "Acknowledge" sends POST to the HA webhook
- Priority `critical` bypasses Do Not Disturb on mobile

---

## How to get the device_id

```
Developer Tools → Template →
{{ device_id('notify.nome_topic') }}
```

Or: Settings → Devices & Services → ntfy → click the topic device.

---

## Notes

- `TargetRequired.NEVER`: the topic target is conveyed via `ntfy_device_id` in `data`,
  not via HA's standard `target` field. This avoids the transport being suppressed
  when no person target is present in the notification call.
- Camera snapshot uses `camera.snapshot` to `/config/www/` (accessible at `/local/`),
  then attaches via `hass_api.abs_url()`. This works for both cloud and local ntfy.
- `_parse_delay()` accepts both `"10m"` / `"1h30m"` shorthand and `"HH:MM"` / `"HH:MM:SS"`.
  Unrecognized formats are passed through with a warning.
