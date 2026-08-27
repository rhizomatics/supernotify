---
tags:
  - transport
  - kodi
---
# Kodi Transport Adaptor

## Motivation

Shows on-screen overlay notifications on Kodi media centers through the Home Assistant
[`kodi`](https://www.home-assistant.io/integrations/kodi/) integration, calling the entity-based
`kodi.call_method` service with the JSON-RPC method `GUI.ShowNotification`. Through the `generic`
transport only the legacy YAML notify platform is reachable; the native transport targets the
modern config-entry integration on any `media_player.kodi_*` entity — no extra YAML, multiple
instances, and the camera snapshot as the overlay icon.

## Features

* Priority-mapped icon — critical → `error`, high → `warning`, medium/low/minimum → `info`,
  overridable with `kodi_icon`.
* Display time with Kodi's 1500 ms minimum enforced (`kodi_displaytime`, default 10000).
* Camera snapshot as the overlay icon (`kodi_attach_image: true`), resolved to a URL the Kodi host
  can fetch: `snapshot_url` when present, otherwise `grab_image()` + the media storage URL.
* Title fallback ("Notification") because `GUI.ShowNotification` requires a non-empty title.

## Configuration

Targets are the Kodi `media_player` entities; other targets are dropped and a delivery with no
valid target fails.

```yaml
delivery:
  kodi_overlay:
    transport: kodi
    target:
      - media_player.kodi_living_room
    data:
      kodi_displaytime: 8000
    selection: explicit
```

The Home Assistant *Internal URL* should be a direct IP (e.g. `http://192.168.0.10:8123`) rather
than an mDNS `.local` hostname, which some players cannot resolve when fetching the snapshot.

## Kodi Data Keys

* `kodi_displaytime` — overlay duration in ms (default 10000, minimum 1500)
* `kodi_icon` — `info` | `warning` | `error` or an image URL; overrides the priority mapping
* `kodi_attach_image` — camera snapshot as the icon (default `false`); a resolved image URL wins over `kodi_icon`

## Notes

* `kodi.call_method` forwards every extra key as a JSON-RPC parameter, which makes the whole
  `GUI.ShowNotification` call fail on the Kodi side: residual generic data keys are therefore
  dropped with a debug log, unlike the standard transport pattern.
* Pure overlay: no action buttons and no user interaction.
