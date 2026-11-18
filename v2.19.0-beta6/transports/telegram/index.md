# Telegram Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/telegram/

| Transport ID | Source                                                                                                                     | Requirements                                                                        | Optional |
| ------------ | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | -------- |
| `telegram`   | [`telegram.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/telegram.py) | [Telegram Bot Integration](https://www.home-assistant.io/integrations/telegram_bot) | -        |

## Motivation

Use the [Telegram Bot](https://www.home-assistant.io/integrations/telegram_bot) integration in Home Assistant for richer telegram notifications, adapting core Supernotify data like title, priority, image and actions, and exposing telegram specific tuning.

## Targets

A chat can be targeted in two ways:

- Its chat id, as a `telegram_chat_id` target, for example `telegram_chat_id:123456789`. Group chat ids are negative numbers
- The `notify` entity the Telegram Bot integration creates for each allowed chat, for example `notify.family_chat`. This also tells Home Assistant which bot to use, so is needed if there's more than one bot

Either selects the `telegram` delivery automatically, without naming it, and a notification can go to several chats at once. A Telegram `notify` entity is sent to by this transport, rather than the generic [`notify_entity`](https://supernotify.rhizomatics.org.uk/latest/transports/notify_entity/index.md) one, so it gets the image, buttons and priority handling.

Example Notification

```yaml
- action: supernotify.notify
  data:
    message: "Motion detected at front door"
    title: "📷 Front Camera"
    target:
      - telegram_chat_id:123456789
      - notify.family_chat
```

A chat id can also be fixed in a delivery's configuration, or given as `telegram_chat_id` in `data`, which overrides the target. Either can be a single id or a list.

## Example configuration

Fixed chat

```yaml
delivery:
  telegram_home:
    transport: telegram
    target:
      telegram_chat_id: 123456789
```

Security channel with camera snapshot

```yaml
delivery:
  telegram_security:
    transport: telegram
    target:
      telegram_chat_id: -987654321
    data:
      telegram_attach_image: true
      telegram_parse_mode: "HTML"
```

Alarm channel with inline buttons

```yaml
delivery:
  telegram_alarms:
    transport: telegram
    inclusion: scenario
    target:
      telegram_chat_id: 123456789
    data:
      telegram_attach_image: true
      telegram_inline_keyboard:
        - - text: "✅ Acknowledge"
            callback_data: "ack_alarm"
          - text: "🔇 Snooze"
            callback_data: "snooze_alarm"
```

A delivery with its own fixed target, like these, is used for every notification unless it has an `inclusion` of `explicit` or `scenario`.

## Example call with a camera

action: supernotify.notify

```yaml
data:
  message: "Motion detected at front door"
  title: "📷 Front Camera"
  delivery: telegram_security
  media:
    camera_entity_id: camera.front_door
```

### Expected behavior

- Telegram receives the camera snapshot as a photo, with the bold title and message as its caption, since `telegram_security` has `telegram_attach_image: true`
- Low and minimum priority notifications arrive silently, using `disable_notification`. Telegram has no way of breaking through Do Not Disturb, so critical and high priority notifications arrive as normal ones

## Data keys

| Key                             | Effect                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| `telegram_parse_mode`           | `HTML`, `Markdown` or `MarkdownV2`. Plain text if not set                                |
| `telegram_disable_notification` | Send silently, or not, whatever the priority                                             |
| `telegram_chat_id`              | Chat id, or list of them, to send to instead of the targets                              |
| `telegram_reply_to_message_id`  | Send as a reply to an earlier message                                                    |
| `telegram_inline_keyboard`      | Buttons, as rows of `{text, callback_data}`, or Home Assistant's own `[label, callback]` |
| `telegram_attach_image`         | Send the notification's image, from its `snapshot_url` or camera, as a photo             |
| `telegram_image_as_document`    | Send the image as a document, without Telegram's compression                             |
| `telegram_protect_content`      | Accepted, but has no effect, since Home Assistant doesn't allow it for these actions     |

These Telegram Bot action fields are also passed on from `data`: `config_entry_id`, `disable_web_page_preview`, `keyboard`, `message_tag`, `message_thread_id`, `one_time_keyboard` and `resize_keyboard`. Anything else in `data` is left out, since the Telegram Bot actions reject fields they don't know, and a notification's `data` is shared with all its deliveries.

Without `telegram_inline_keyboard`, Supernotify's own [actions](https://supernotify.rhizomatics.org.uk/latest/usage/mobile_actions/index.md) become buttons, up to 5, other than notification level actions.

## Formatting

- The title is shown in bold above the message. With `HTML`, the title is escaped, but not the message, so it can contain tags. With `Markdown` or `MarkdownV2`, the title's special characters are escaped, so a title like `Alert!` doesn't stop Telegram parsing the message
- A message longer than Telegram's 4096 characters, or a caption longer than 1024, is cut short, and sent as plain text, since the cut could leave a tag or markup unfinished

## Images

The image is sent as a file from the Supernotify media folder, which Home Assistant only allows if it's in `allowlist_external_dirs` - see [Multimedia Basic Configuration](https://supernotify.rhizomatics.org.uk/latest/configuration/multimedia/#basic-configuration). Without one, or if no image can be got, the message is sent as text.

## How to get the chat_id

1. Start a chat with your bot on Telegram (send /start)
1. Visit: https://api.telegram.org/bot\<YOUR_TOKEN>/getUpdates
1. Find "chat" → "id" in the response

The chat also has to be one of the bot's allowed chats in the Telegram Bot integration, which is where its `notify` entity comes from. Use the `telegram_bot.send_message` action in Home Assistant Developer Tools to test a chat id before using it in Supernotify.

## Discovery

**Delivery (default selection).** If the `telegram_bot` integration is configured and no `telegram` delivery is defined, a `telegram` delivery is generated automatically. It's used for any notification with a `telegram_chat_id` target, or one of the integration's own `notify` entities, and otherwise skipped.

## Notes

- Chat ids are sent to Home Assistant as `chat_id`, rather than the deprecated `target`, which raises a repair issue
- The action switches between `telegram_bot.send_message`, `send_photo` and `send_document`, depending on whether an image is attached, and how
- `TransportFeature.SNAPSHOT_IMAGE` is declared so the Supernotify scheduler waits for PTZ cameras to complete their rotation before dispatching
