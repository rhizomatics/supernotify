---
tags:
  - transport
  - html5
---
# HTML5 Browser Push Transport Adaptor

## Motivation

Provides a native SuperNotify transport for browser web push through the Home Assistant
[`html5`](https://www.home-assistant.io/integrations/html5/) integration. The transport calls
the modern `html5.send_message` entity service rather than the legacy `notify.html5` platform:
the legacy platform reads `ttl` and `priority` from keyword arguments the notify bridge never
populates, so urgency would silently always be "normal". With the entity service, urgency is
mapped natively from the SuperNotify priority.

## Features

* Urgency mapped from priority — critical/high → `high`, medium → `normal`, low/minimum → `low`,
  overridable with `html5_urgency`.
* Tags and renotify, so a repeated alert replaces the previous one instead of piling up.
* Action buttons (`html5_actions`); clicks fire `html5_notification.clicked` events carrying the
  action value, ready for actionable-notification automations.
* Camera snapshot as the notification image (`html5_attach_image: true`) using the shared media
  pipeline — the URL must be reachable by the browser, so an HTTPS `external_url` (or Home
  Assistant Cloud) is usually required.
* `silent` and `vibrate` are mutually exclusive in the core schema (`vol.Exclusive`): the transport
  never sends both, and logs a warning when it has to drop one.

## Configuration

Targets are the `notify.*` entities created by browser registrations (html5 config entry with
VAPID keys). Non-matching targets are dropped; a delivery with no valid target fails.

```yaml
delivery:
  browser_push:
    transport: html5
    target:
      - notify.chrome_laptop
      - notify.firefox_phone
    data:
      html5_tag: supernotify
      html5_renotify: true
    selection: explicit
```

## HTML5 Data Keys

* `html5_urgency` — `low` | `normal` | `high` (default mapped from priority)
* `html5_tag` — notifications sharing a tag replace each other
* `html5_actions` — list of `{action, title, icon}` buttons
* `html5_attach_image` — camera snapshot as `image` URL (default `false`)
* `html5_icon`, `html5_badge` — icon / badge URLs
* `html5_url` — URL opened on click (sent as `data.url`)
* `html5_require_interaction` — keep on screen until the user interacts
* `html5_renotify` — alert again when a new notification replaces an existing tag
* `html5_silent` — suppress sound/vibration (exclusive with `html5_vibrate`)
* `html5_vibrate` — vibration pattern in ms, e.g. `[200, 100, 200]`
* `html5_ttl` — time-to-live in seconds or an HA duration mapping
* `html5_data` — extra keys merged into the custom `data` field (`html5_url` wins on `url`)

## Notes

* The `html5.send_message` schema is a strict whitelist: unknown top-level keys fail the whole
  call, so residual generic data keys are not forwarded (debug log); `html5_data` is the explicit
  passthrough.
* `title` is required by the schema; without a title the HA default "Home Assistant" is used.
* Expired push subscriptions (410 GONE) are handled by the core, which unregisters the browser
  and raises: the delivery is then reported as failed.
