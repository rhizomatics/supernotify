---
title: Why Notifications Are Hard
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Why sending one notification to email, Telegram, mobile push and SMS is hard in Home Assistant, with a catalog of the different notification action styles and how each integration uses them
---
# Why Notifications Are Hard in Home Assistant

This page explains why one message to several channels is harder than it looks in Home Assistant. It is the reason
Supernotify exists, and it is also meant as a contribution to the current Home Assistant work on making
notifications easier. It describes Home Assistant **2026.11**, checked against its source code. Each release moves
more integrations to notify entities, so some rows of the [table](#integrations-and-their-styles) will change.

## "Why can't I just use a group?"

Say you want one alert to reach your phone, your e-mail, a family Telegram chat and an SMS to someone without
a smartphone. Home Assistant has notify groups, so it seems natural to make a group of those four and send to it.
There are two kinds of notify group, and neither can hold all four.

**The Notify group helper**, set up in the UI, groups **notify entities** and sends with `notify.send_message`.
The Companion App, SMTP and Telegram bot all have notify entities, so three of the four can go in. SMS can't: the
SMS integrations, such as Twilio SMS and ClickSend, only have the older style of notify action. The group sends only a
`message` and a `title`, and it drops the title for everyone if any member doesn't support titles. There is no way to
add a camera snapshot, a button on the phone notification, an HTML e-mail body or anything else.

**The legacy notify group**, YAML only, groups the older **notify actions**, like `notify.mobile_app_annas_phone`
or `notify.smtp`. Telegram can't go in, because its notify action was removed in 2026.11 and only the notify entity
is left. The other three can, but every member gets the same call:

- `target` means something different to each one: e-mail addresses to SMTP and phone numbers to Twilio, while a
  phone's own action ignores it. One `target` can't be right for all of them.
- `data` is sent to every member whatever its keys. A picture is `data.image` for the Companion App, `data.images`
  (a list of local files) for SMTP and `data.media_url` for Twilio SMS. Each member gets the keys meant for the
  others as well as its own.
- Each member can have fixed `data` set in the YAML, but not data that changes per notification, such as an
  image for this alert.

Neither kind of group knows who it is notifying. When a phone is replaced, the group has to be edited. If someone is
away, or the message should only go to whoever is at home, the group can't decide that. Groups are just fixed lists
of where to send.

## Why it's like this

None of this is anyone's mistake. Home Assistant has added hundreds of notification integrations over ten years,
each with the needs of its own service, and the shared part of notifications has always been very small:

- **Only `message` is common.** `title` is common to most actions. `target` exists in one style and not in the
  others, and means something different in each integration. Everything else (images, buttons, priority, sound,
  HTML, attachments, tap actions) goes under a free-form `data` key in the legacy style, or into fields of an
  integration's own action in the newer style. No shared schema covers them.
- **The same idea has different names.** A tap action is `data.url` on iOS but `data.clickAction` on Android, both
  in the Companion App. It is `click` in ntfy and `url` in Prowl and Pushover. Priority is `-2` to `2` in Pushover and
  Prowl, `1` to `5` in ntfy, `info`/`warning`/`critical` in LaMetric, and `interruption-level` under `push` for the
  iOS Companion App.
- **Some services have an action per target.** The legacy Companion App style makes a `notify.mobile_app_<device>`
  action for every phone, so the action name is the target. Automations name the phone, not the person, and have
  to be changed when the phone is replaced.
- **Some services have two styles at once.** Newer integrations offer a notify entity, which works with
  `notify.send_message`, areas, labels and groups but sends only message and title. For everything else, they add an
  action of their own that is aimed at the same entity, such as `smtp.send_message` or `ntfy.publish`. To use an
  image, you have to leave the shared action for the integration's own action.
- **Speech, chimes and on-screen messages are separate again.** `tts.speak`, `persistent_notification.create`,
  `alexa_devices.send_sound` and `mqtt.publish` each have their own shape and targets, and none of them is a notify
  action.

Notify entities are the right direction: they can be targeted by area, label and device, and they show up properly
in the UI. They don't yet carry anything beyond message and title, though, and many integrations, especially SMS,
haven't moved to them.

## The styles of notification action

### 1. Legacy notify action for a service

One action for each configured service, with a shared shape: `message`, `title`, `target` and a free-form
`data`. The meaning of `target` and the keys in `data` belong to each integration.

```yaml
action: notify.smtp
data:
  title: Front door
  message: The front door has been open for 10 minutes
  target:
    - anna@example.com
  data:
    images:
      - /config/www/snapshots/front_door.jpg
```

The same action for Twilio SMS takes phone numbers as `target` and `media_url` in `data`.

### 2. Legacy notify action for a device

Same shape as style 1, but the integration makes one action per device, so the target is in the action name.
The Companion App is the main example, with `notify.mobile_app_<device>` for each phone, and different `data` keys
for iOS and Android.

```yaml
action: notify.mobile_app_annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
  data:
    image: /api/camera_proxy/camera.front_door
    url: /lovelace/doors          # iOS
    clickAction: /lovelace/doors  # Android
    actions:
      - action: CLOSE_DOOR
        title: Close it
```

### 3. Notify entity with `notify.send_message`

One shared action for every notify entity, which can be targeted by entity, device, area or label, and is
fully supported in the UI editor. It takes only `message` and `title`, and the title is used only by entities that
declare support for it. There is no `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. The integration's own action, aimed at its notify entity

The integration's notify entity is used for the target, and the integration adds its own action with flat fields
for everything `notify.send_message` can't send. The fields differ for each integration.

```yaml
action: ntfy.publish
target:
  entity_id: notify.ntfy_alerts
data:
  title: Front door
  message: The front door has been open for 10 minutes
  priority: 4
  click: https://my.home/lovelace/doors
  attach: https://my.home/local/snapshots/front_door.jpg
```

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` and the
`telegram_bot.send_*` actions work the same way, each with different fields.

### 5. The integration's own action, with its own targets

Actions that aren't based on notify at all, and pick their target their own way: a device, a room, a topic, or a
media player alongside a TTS engine.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Others are `lametric.message` (by `device_id`), `alexa_devices.send_sound` (by `device_id`), `matrix.send_message`
(by room), `mqtt.publish` (by topic) and `persistent_notification.create` (no target, it appears in the
Home Assistant UI).

### 6. Groups

The two kinds of notify group are described [above](#why-cant-i-just-use-a-group). The Notify group helper is a
notify entity used with style 3. The legacy notify group is a style 1 action that calls other style 1 or 2
actions.

## Integrations and their styles

Home Assistant 2026.11. **Both** means the integration has two styles, where the notify entity is the easy one
and the other is needed for anything beyond message and title.

| Integration             | Legacy action (1 or 2)                   | Notify entity (3)              | Own action (4 or 5)                              | Beyond message and title                          |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Both**, per phone            | -                                                | Legacy `data`: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (e-mail)           | `notify.<name>`, `target` = addresses    | **Both**, per recipient        | `smtp.send_message` (4)                          | Legacy `data.images`, `data.html`; own action `html`, `attachments`, `priority` |
| Telegram bot            | Removed in 2026.11                       | Yes, per chat                  | `telegram_bot.send_message`, `send_photo`, ... (4) | Own actions: `keyboard`, `inline_keyboard`, `parse_mode`, separate actions for photos and files |
| Twilio SMS              | `notify.<name>`, `target` = numbers      | No                             | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = numbers      | No                             | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = numbers      | No                             | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = devices      | No                             | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = channels     | No                             | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = channel IDs | **Both**, per channel, no title | -                                               | Legacy `data.images`, `data.embed`, `data.urls`   |
| Matrix                  | `notify.<name>`, `target` = rooms        | No                             | `matrix.send_message` (5)                        | `data.images`                                     |
| HTML5 push              | `notify.<name>`, `target` = registrations | **Both**                      | `html5.send_message` (4)                         | Own action: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Both**                       | `ntfy.publish` (4)                               | Own action: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, deprecated              | **Both**, no title             | `prowl.send_message` (4)                         | Own action: `priority`, `url`                     |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Both**                       | `nfandroidtv.send_message` (4)                   | Own action: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Both**, no title             | `lametric.message` by device (5)                 | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | No (proposed)                  | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | No                             | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Both**, speak and announce per device | `alexa_devices.send_sound` by device (5) | Sounds only through the own action              |
| Text-to-speech          | `notify.<name>` (YAML `platform: tts`)   | No                             | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Persistent notification | `notify.persistent_notification`         | No                             | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Yes, no title                  | `mqtt.publish` by topic (5)                      | Any payload                                       |

## Notifying a person, not a device

Home Assistant knows who each person is and which device trackers follow them, but not how to reach them. The
Home Assistant team is working on this, after the community "What the Heck?" discussion
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), with a
proposal in [architecture discussion #1552](https://github.com/home-assistant/architecture/discussions/1552):
each person gets a list of their notify entities, and `notify.send_message` can be sent to `person.anna`. That
fixes the biggest everyday problem, replacing the phone in every automation, and makes notify entities the
natural way to reach someone.

Supernotify will support this as soon as possible once it is released, both by sending to a person through their
linked notify entities and by letting `notify.send_message` to a person go through Supernotify's own routing.

## What Supernotify does about it

Supernotify takes one notification, with one set of options, and turns it into the right call for each channel:

- **One action for everything.** `supernotify.notify` takes the message, title, images, buttons and priority once,
  and each [transport](../transports/index.md) maps what its channel supports onto the style, field names and
  targets its integration needs, whether legacy action, notify entity, own action or TTS.
- **People, not devices.** [Recipients](../configuration/people.md) hold each person's e-mail, phone number, Telegram
  chat and so on, and their Companion App phones are found automatically. Notify `person.anna` and each channel
  gets the right address. Each recipient also gets its own notify entity.
- **Who should get it.** Notifications can go only to people at home, or only to those away, and fall back to
  other channels or people. See the [presence routing with fallback](../recipes/presence_routing_with_fallback.md)
  recipe.
- **What it's about.** [Scenarios](../configuration/scenarios.md) and priorities decide which channels to use, so a
  low priority message can go only to the phone while a critical one also sounds chimes and speaks on speakers.
- **Not too often.** [Snoozing](../usage/snoozing.md) and [duplicate detection](../configuration/dupe_detection.md)
  stop the same alert repeating.
