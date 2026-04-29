---
tags:
  - transport
  - telegram
---
# Telegram Transport Adaptor

## Motivation

Use the latest [Telegram Bot](https://www.home-assistant.io/integrations/telegram_bot) integration in Home Assistant for richer telegram notifications, adapting core Supernotify data like title and image, and exposing telegram specific tuning.


## Testing

Tested on Home Assistant 2026.3.4 with `telegram_bot` platform: polling

## Example configuration

```yaml title="Basic Configuration"
telegram_home:
  transport: telegram
  selection: default
  data:
    telegram_chat_id: 123456789
```

```yaml title="security channel with camera snapshot"
telegram_security:
  transport: telegram
  selection: default
  data:
    telegram_chat_id: 123456789
    telegram_attach_image: true
    telegram_parse_mode: "HTML"
```

```yaml title="Alarm channel with inline buttons"
telegram_alarms:
  transport: telegram
  selection: scenario
  data:
    telegram_chat_id: 123456789
    telegram_attach_image: true
    telegram_inline_keyboard:
      - - text: "✅ Acknowledge"
          callback_data: "ack_alarm"
        - text: "🔇 Snooze"
          callback_data: "snooze_alarm"
```
## Example call

```yaml title="action: notify.supernotify"
data:
  message: "Motion detected at front door"
  title: "📷 Front Camera"
  data:
    media:
      camera_entity_id: camera.ezviz_ingresso
```

### Expected behavior

* Telegram receives photo with bold title as caption
* Low-priority notifications arrive silently
<* Critical notifications bypass Do Not Disturb

## How to get the chat_id

1. Start a chat with your bot on Telegram (send /start)
2. Visit: https://api.telegram.org/bot&lt;YOUR_TOKEN&gt;/getUpdates
3. Find "chat" → "id" in the response

Or use the `telegram_bot.send_message` service from HA Developer Tools to test
with your chat_id before committing it to `delivery.yaml`


## Notes

* `TargetRequired.ALWAYS`: `chat_id` is always required — either from `delivery.target`
(configured in `delivery.yaml`) or from the `telegram_chat_id` data key.
* Direct `hass_api.call_service()` is used instead of `call_action()` because the
service name switches dynamically between `send_message`, `send_photo`, and
`send_document` depending on whether a snapshot is attached.
* `grab_image()` (not `snap_notification_image()`) handles reprocessing: resize,
JPEG/PNG optimisation, metadata removal, and per-filename caching for multiple
deliveries with the same settings.
* `TransportFeature.SNAPSHOT_IMAGE` is declared so the SuperNotify scheduler
waits for PTZ cameras to complete their rotation before dispatching (v1.14.0+).</li>
* HTML special characters in title and message are escaped via `html.escape()`
when `parse_mode=HTML`, preventing accidental tag injection.
