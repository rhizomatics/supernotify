---
tags:
  - transport
  - discord
---
# Discord Transport Adaptor

## Motivation

Provides a native SuperNotify transport for [Discord](https://discord.com/) through the
Home Assistant `discord` integration. Through the `generic` transport only plain text
reaches Discord; the native transport adds markdown title composition, rich embeds,
camera snapshot upload, remote image URLs and an optional priority emoji prefix.

## Features

* Title composed into the message body as Discord markdown (`**title**` + newline + message),
  skipped automatically when a `discord_embed` carries its own `title`.
* Rich embeds passed through to the service (`title`, `description`, `color`, `url`,
  `fields`, `footer`, `author`, `thumbnail`, `image` — Home Assistant core schema).
* Camera snapshot attachment via `envelope.grab_image()` (`discord_attach_image: true`),
  waiting for camera PTZ to complete before sending.
* Remote image URLs forwarded as `urls`, with optional SSL verification control.
* Opt-in emoji prefix derived from the SuperNotify priority (critical, high, low/minimum).
* Message content truncated to the Discord hard limit of 2000 characters, so a long
  message is delivered rather than rejected.

## Configuration

The `discord` integration is set up in Home Assistant with a bot token. The bot must be
invited to the server with the *Send Messages* permission. The action name depends on the
config entry (`notify.discord`, `notify.discord_2`, …), so any `notify.*` action is accepted.

Targets are numeric Discord channel or user IDs (Developer Mode → *Copy ID*). A target is
required: non-numeric entries are dropped and a delivery with no valid target fails.

```yaml
delivery:
  discord_alerts:
    transport: discord
    action: notify.discord
    target:
      - "123456789012345678"
    data:
      discord_priority_prefix: true
    selection: explicit
```

For camera snapshots (`discord_attach_image`) the `discord` integration checks local paths
with `is_allowed_path`, so the SuperNotify media path must be listed:

```yaml
homeassistant:
  allowlist_external_dirs:
    - /config/supernotify/media
```

For `discord_image_urls` every URL must be covered by `allowlist_external_urls`; the
integration downloads at most 8MB per attachment.

## Discord Data Keys

* `discord_embed` — embed mapping passed through as `data.embed`. `color` is an integer
  (`0xFF0000` in YAML is `16711680`); hex strings are passed through unchanged and may be
  rejected downstream.
* `discord_attach_image` — attach the camera snapshot as a local file in `data.images` (default `false`)
* `discord_image_urls` — list of image URLs forwarded as `data.urls` (a single string is wrapped)
* `discord_verify_ssl` — SSL verification for URL downloads (only forwarded when set)
* `discord_priority_prefix` — prefix the message with a priority emoji (default `false`)

Example call with an embed and a snapshot:

```yaml
action: supernotify.notify
data:
  title: "Alarm"
  message: "Motion detected"
  data:
    priority: critical
    delivery:
      discord_alerts:
        data:
          discord_attach_image: true
          discord_embed:
            title: "Garden camera"
            description: "Motion at 22:41"
            color: 15158332
```

## Notes

* Discord has no native message priority: the emoji prefix is the only mapping offered.
* Unknown residual `data` keys are not forwarded to the service (they would be ignored
  downstream anyway); a debug log lists what was dropped.
