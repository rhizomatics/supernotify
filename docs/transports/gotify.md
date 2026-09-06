---
tags:
  - transport
  - gotify
---
# Gotify Transport Adaptor

## Motivation

Access Gotify's richer features: click-through URLs, `bigImageUrl` (expanded image on notification tap), Markdown rendering, and Android intent actions on receive. Requires
the [homeassistant-gotify](https://github.com/1RandomDev/homeassistant-gotify) HACS integration

## Notes

- **`action:` is required** — unlike most transports, there is no default
  action. The HACS integration lets users name the service freely
  (`notify.gotify`, `notify.my_server`, etc.), so `validate_action()` accepts
  any `notify.*` service and warns if the action is missing or uses the wrong
  domain.
- **Camera snapshot** — `gotify_attach_image: true` triggers a
  `camera.snapshot` call and builds a publicly-reachable URL. `gotify_image_url` (explicit URL) takes precedence and skips the snapshot entirely.
- **No raw_data passthrough** — the HACS payload schema is fixed
  (`{message, title, data: {priority, extras}}`). Unknown keys would cause
  silent failures or future breakage; they are intentionally dropped (documented
  with an inline comment).
- **Separate snapshot path** — uses `supernotify_gotify_snapshot.jpg` (not the
  ntfy snapshot path) to prevent race conditions when both transports fire
  concurrently.

---

## Testing

Tested on Home Assistant 2026.3.4 with:
- Gotify server v2.4.0 (self-hosted, local network)
- HACS integration `1RandomDev/homeassistant-gotify` v1.0.2
- SuperNotify v1.12.2

**Test cases verified on real HA:**

```yaml
# 1. Basic message — priority auto-mapping
action: supernotify.notify
data:
  message: "Test base Gotify"
  title: "SuperNotify Test"
  delivery: [gotify_base]
# Result: notification received, priority=5 (int) in Gotify ✅

# 2. Critical alert — priority mapping
action: supernotify.notify
data:
  message: "Allarme ingresso attivo"
  title: "🚨 Allarme"
  delivery: [gotify_base]
  priority: critical
# Result: priority=10, notification shown with max urgency ✅

# 3. With bigImageUrl from camera snapshot
action: supernotify.notify
data:
  message: "Movimento rilevato"
  delivery: [gotify_con_camera]
  data:
    gotify_attach_image: true
  media:
    camera_entity_id: camera.ingresso
# Result: snapshot taken, bigImageUrl present, image visible on tap ✅

# 4. With click URL and Markdown
action: supernotify.notify
data:
  message: "**Porta aperta** — controlla la dashboard"
  delivery: [gotify_base]
  data:
    gotify_click: "https://ha.local:8123/lovelace/sicurezza"
    gotify_markdown: true
# Result: bold text rendered, tap opens HA dashboard ✅

# 5. Missing action: — validate_action warning
# Delivery configured without action: notify.*
# Result: warning logged, delivery suppressed, no crash ✅
```

**Unit tests:** `tests/components/supernotify/test_transport_gotify.py`
- 35 test cases covering: `_build_extras()` (all combinations), `validate_action()`,
  `deliver()` happy path, all 5 priority levels, `gotify_priority` override
  (int/string/clamp/invalid), `boolify()` behaviour for YAML strings,
  `gotify_image_url` precedence over `attach_image`, camera snapshot success/failure,
  no `gotify_*` key leakage into payload, service exception handling,
  `supported_features`, `default_config`.

---

## Priority mapping reference

| SuperNotify | Gotify int | Gotify label |
|-------------|-----------|--------------|
| `critical`  | 10        | max urgency  |
| `high`      | 7         | high         |
| `medium`    | 5         | default      |
| `low`       | 2         | low          |
| `minimum`   | 0         | silent/min   |

---

## Configuration example

```yaml
# configuration.yaml (HA)
notify:
  - platform: gotify
    name: gotify
    url: http://gotify.local
    token: !secret gotify_token

# supernotify/delivery.yaml
deliveries:
  gotify_allarme:
    transport: gotify
    action: notify.gotify          # REQUIRED
    priority: high
    data:
      gotify_click: "https://ha.local:8123/lovelace/sicurezza"
      gotify_attach_image: true
      gotify_markdown: true

  gotify_info:
    transport: gotify
    action: notify.gotify
    priority: low                  # → Gotify priority 2
```

---

## Deviations from standard patterns (intentional)

**No `raw_data` passthrough** (CLAUDE.md §4 pattern): The standard pattern
passes residual `raw_data` keys to `action_data`. For Gotify this is
deliberately omitted — the HACS service has a fixed schema and unknown top-level
keys cause silent failures or HTTP 400s on future integration updates. This
decision is documented with an inline comment in `deliver()`.

**No default `action:`**: All other transports set `config.delivery_defaults.action`.
Gotify cannot because the service name is user-controlled. `validate_action()`
provides a clear warning when `action:` is missing.

---

## Related

- Fixes the `generic` transport workaround for Gotify (priority string bug)
- Follows the same transport pattern as the ntfy transport (PR #TBD)
- HACS integration: https://github.com/1RandomDev/homeassistant-gotify
- Gotify extras docs: https://gotify.net/docs/msgextras
