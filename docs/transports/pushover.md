---
tags:
  - transport
  - pushover
---
# Pushover Transport Adaptor

## Motivation

Provides a native SuperNotify transport for [Pushover](https://pushover.net/), the
popular push notification service with excellent iOS and Android apps.
Implements full Pushover API coverage including emergency mode with automatic
retry/expire management and camera snapshot attachment via grab_image().

## Features

* 5-level priority mapping — SuperNotify critical/high/medium/low/minimum
maps to Pushover -2…2 integers automatically.
* Emergency mode (priority=2) — Pushover requires retry and expire.
* SuperNotify auto-supplies sensible defaults (60s / 3600s) when not
explicitly configured, with a debug log noting the values used.
* Parameter clamping — retry clamped to minimum 30s, expire clamped
to maximum 10800s (3h), matching Pushover API limits.
* Camera snapshot attachment — pushover_attach_image: true calls
grab_image() (v1.14.0+ API), correctly declares
* Waits for the camera PTZ to complete before sending.

## Pushover Data Keys

Data keys covering the full Pushover feature set:

* `pushover_priority`
* `pushover_sound`
* `pushover_url`
* `pushover_url_title`
* `pushover_retry`
* `pushover_expire`
* `pushover_callback`
* `pushover_html`
* `pushover_ttl`
* `pushover_device`
* `pushover_attach_image`

## Configuration

### Add Pushover to Home Assistant
```yaml title="Home Assistant Configuration"
notify:
  - name: pushover_home
    platform: pushover
    api_key: "YOUR_PUSHOVER_API_KEY"
    user_key: "YOUR_PUSHOVER_USER_KEY"
```

### Add Pushover to Supernotify

#### Minimal

```title="Supernotify Configuration"
pushover_home:
  transport: pushover
  action: notify.pushover_home   # REQUIRED — must match configuration.yaml name
  selection: default
```

#### Maxmimal
```title="Supernotify Configuration"
pushover_home:
  transport: pushover
  action: notify.pushover_home
  selection: default
  data:
    pushover_sound: "siren"
    pushover_url: "https://homeassistant.local:8123"
    pushover_url_title: "Open HA"
    pushover_html: false
    pushover_ttl: 3600
    pushover_device: "iphone"        # send to specific device only
    pushover_attach_image: true      # attach camera snapshot
```

#### Emergency delivery
Activates when priority=critical or via scenario

```title="Supernotify Configuration"
pushover_emergency:
  transport: pushover
  action: notify.pushover_home
  selection: scenario
  data:
    pushover_sound: "siren"
    pushover_retry: 60               # repeat every 60s (min 30)
    pushover_expire: 1800            # stop after 30 min (max 10800)
    pushover_callback: "http://homeassistant.local:8123/api/webhook/pushover_ack"
```
### Example Call

```yaml
action: notify.supernotify
data:
  message: "Test transport nativo Pushover - Se ricevi con suono magic, funziona!"
  title: "PR Pushover Smoke Test"
  data:
    delivery_selection: fixed
    delivery:
      pushover_test:
        enabled: true
```

#### Resulting Notification Archive

```json
{
  "delivered": 1, "failed": 0, "error_count": 0,
  "stats": { "total_duration_ms": 3.0, "delivery_success_rate": 1.0 },
  "deliveries": {
    "pushover_test": {
      "delivered": [{
        "calls": [{
          "domain": "notify", "action": "pushover",
          "action_data": {
            "message": "Test transport nativo Pushover - ...",
            "title": "PR Pushover Smoke Test",
            "data": { "priority": 0, "sound": "magic" }
          },
          "elapsed": 0.003,
          "failed_calls": []
        }]
      }]
    }
  }
}
```
