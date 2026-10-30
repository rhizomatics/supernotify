# Pushover Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/pushover/

## Motivation

Provides a native SuperNotify transport for [Pushover](https://pushover.net/), the popular push notification service with excellent iOS and Android apps. Implements full Pushover API coverage including emergency mode with automatic retry/expire management and camera snapshot attachment via grab_image().

## Features

- 5-level priority mapping — SuperNotify critical/high/medium/low/minimum maps to Pushover 2…-2 automatically, or override with `pushover_priority`.
- Emergency mode (priority 2, so `critical`) — Pushover requires `retry` and `expire`, so 60s / 3600s are supplied when not configured. A `retry` under 30s is raised to 30s, and an `expire` over 10800s (3h) lowered to 10800s.
- Camera snapshot attachment — `pushover_attach_image: true` grabs the camera image, waiting for any camera PTZ to complete before sending.
- Send to selected devices with `pushover_device`.

## Pushover Data Keys

- `pushover_priority` — `-2` to `2`, overriding the priority mapping; anything else is ignored
- `pushover_sound` — a [Pushover sound](https://pushover.net/api#sounds), such as `siren`
- `pushover_url` / `pushover_url_title` — a link shown with the notification, and its label
- `pushover_retry` — seconds between repeats for an emergency, minimum 30, default 60
- `pushover_expire` — seconds before an emergency stops repeating, maximum 10800, default 3600
- `pushover_callback` — public URL Pushover calls when an emergency is acknowledged, such as a Home Assistant webhook
- `pushover_html` — allow HTML formatting in the message (default `false`)
- `pushover_ttl` — seconds before the notification is deleted from the device
- `pushover_device` — a device name, or list of names, as configured in Pushover; default is all devices
- `pushover_tags` — a tag, or list of tags, so an emergency can be cancelled with Home Assistant's `pushover.cancel` action, by tag; an emergency without tags can only be acknowledged in the Pushover app
- `pushover_attach_image` — attach the camera snapshot (default `false`)

`pushover_retry`, `pushover_expire` and `pushover_callback` only apply to an emergency. Any other `data` key isn't passed on, since the Pushover action rejects what it doesn't know. Pushover's `timestamp` isn't supported.

## Configuration

### Add Pushover to Home Assistant

Add the [Pushover integration](https://www.home-assistant.io/integrations/pushover/) from *Settings → Devices & services*, with your API token and user key. The old `platform: pushover` YAML is no longer used.

For `pushover_attach_image`, the Supernotify media folder must be in Home Assistant's allowed paths, or the integration refuses the attachment:

Home Assistant Configuration

```yaml
homeassistant:
  allowlist_external_dirs:
    - /config/supernotify/media
```

### Add Pushover to Supernotify

#### Minimal

Supernotify Configuration

```yaml
delivery:
  pushover_home:
    transport: pushover
    action: notify.pushover_home   # the notify action the integration created
    inclusion: default             # send every notification to Pushover
```

#### Maximal

Supernotify Configuration

```yaml
delivery:
  pushover_home:
    transport: pushover
    action: notify.pushover_home
    inclusion: default
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

Sent as an emergency when the notification priority is `critical`, or if `pushover_priority: 2` is set. This one is only used where a scenario selects it.

Supernotify Configuration

```yaml
delivery:
  pushover_emergency:
    transport: pushover
    action: notify.pushover_home
    inclusion: scenario
    data:
      pushover_sound: "siren"
      pushover_retry: 60               # repeat every 60s (min 30)
      pushover_expire: 1800            # stop after 30 min (max 10800)
      pushover_callback: "http://homeassistant.local:8123/api/webhook/pushover_ack"
      pushover_tags: alarm             # lets pushover.cancel stop it by tag
```

### Example Call

```yaml
action: supernotify.notify
data:
  message: "Pushover smoke test - if you hear the magic sound, it works!"
  title: "Pushover Smoke Test"
  delivery_selection: fixed
  delivery:
    pushover_home:
      data:
        pushover_sound: magic
```

#### Resulting Notification Archive

```json
{
  "delivered": 1, "failed": 0, "error_count": 0,
  "stats": { "total_duration_ms": 3.0, "delivery_success_rate": 1.0 },
  "deliveries": {
    "pushover_home": {
      "delivered": [{
        "calls": [{
          "domain": "notify", "action": "pushover_home",
          "action_data": {
            "message": "Pushover smoke test - ...",
            "title": "Pushover Smoke Test",
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

## Discovery

**Default delivery.** If the Pushover integration is already configured and no `pushover` delivery is defined, a `pushover` delivery is generated automatically, using the integration's `notify` action. It isn't used unless asked for, since a Pushover account has no target to recognise it by: name it in `delivery`, a scenario or a recipient, or define your own delivery with `inclusion: default` to send every notification to Pushover. For several Pushover accounts, define a delivery for each, with its `action`.
