---
title: 为什么通知很难
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: 为什么在 Home Assistant 中把同一条通知同时发送到电子邮件、Telegram、手机推送和短信很难，附通知动作各种风格的目录，以及每个集成如何使用它们
---
# 为什么在 Home Assistant 中通知很难

本页解释为什么在 Home Assistant 中把一条消息发送到多个渠道比看起来更难。这正是 Supernotify 存在的原因，本页也希望为
Home Assistant 当前简化通知的工作贡献一份力量。内容描述的是 Home Assistant **2026.11**，并已对照其源代码核实。每个版本都有更多
集成迁移到 notify 实体，因此[表格](#integrations-and-their-styles)中的部分行会发生变化。

## “为什么不能直接用一个组？” { #why-cant-i-just-use-a-group }

假设你希望一条警报同时送达你的手机、你的邮箱、一个家庭 Telegram 群聊，并通过短信发给一位没有智能手机的人。Home Assistant 有
notify 组，所以把这四个放进一个组然后发送给它，看起来理所当然。notify 组有两种，但没有一种能同时容纳这四个。

**Notify 组助手**在界面中创建，它把 **notify 实体**组合在一起，并通过 `notify.send_message` 发送。Companion App、SMTP 和
Telegram 机器人都有 notify 实体，所以四个中有三个可以加入。短信不行：Twilio SMS 和 ClickSend 等短信集成只有旧式的 notify
动作。这个组只发送 `message` 和 `title`，并且只要有一个成员不支持标题，就会对所有成员去掉标题。无法添加摄像头快照、手机通知上的
按钮、HTML 邮件正文或其他任何内容。

**旧式 notify 组**只能用 YAML 配置，它把旧式的 **notify 动作**组合在一起，例如 `notify.mobile_app_annas_phone` 或
`notify.smtp`。Telegram 无法加入，因为它的 notify 动作已在 2026.11 中移除，只剩下 notify 实体。其余三个可以加入，但每个成员
收到的都是同一个调用：

- `target` 对每个成员的含义都不同：对 SMTP 是电子邮件地址，对 Twilio 是电话号码，而手机自己的动作会忽略它。一个 `target`
  不可能对所有成员都正确。
- `data` 不管包含哪些键，都会发给每个成员。图片对 Companion App 是 `data.image`，对 SMTP 是 `data.images`(本地文件列表)，
  对 Twilio SMS 是 `data.media_url`。每个成员除了收到自己的键，也会收到给其他成员的键。
- 每个成员可以在 YAML 中设置固定的 `data`，但不能设置随每条通知变化的数据，比如这条警报的图片。

两种组都不知道自己在通知谁。换了手机，就要编辑组。如果有人外出，或者消息只应发给在家的人，组无法做出判断。组只是固定的发送目标
列表。

## 为什么会这样 { #why-its-like-this }

这不是谁的错。十年来，Home Assistant 增加了数百个通知集成，每个都按照自身服务的需求设计，而通知的共同部分一直非常小：

- **只有 `message` 是共同的。** 大多数动作都有 `title`。`target` 只存在于一种风格中，而且在每个集成中含义都不同。其他一切
  (图片、按钮、优先级、声音、HTML、附件、点击动作)在旧式风格中放在自由格式的 `data` 键下，在新式风格中则放在集成自己动作的
  字段里。没有任何共同的结构能涵盖它们。
- **同一个概念有不同的名字。** 点击动作在 iOS 上是 `data.url`，在 Android 上却是 `data.clickAction`，两者都属于
  Companion App。在 ntfy 中是 `click`，在 Prowl 和 Pushover 中是 `url`。优先级在 Pushover 和 Prowl 中是 `-2` 到 `2`，在
  ntfy 中是 `1` 到 `5`，在 LaMetric 中是 `info`/`warning`/`critical`，在 iOS 的 Companion App 中则是 `push` 下的
  `interruption-level`。
- **有些服务每个目标一个动作。** Companion App 的旧式风格为每部手机创建一个 `notify.mobile_app_<device>` 动作，所以动作名就是
  目标。自动化指定的是手机而不是人，换手机时就必须修改。
- **有些服务同时有两种风格。** 较新的集成提供 notify 实体，它可以配合 `notify.send_message`、区域、标签和组使用，但只能发送
  消息和标题。对于其他内容，它们会添加针对同一实体的自有动作，例如 `smtp.send_message` 或 `ntfy.publish`。要发送图片，就得放弃
  共同的动作，改用集成自己的动作。
- **语音、门铃提示音和屏幕消息又是另一回事。** `tts.speak`、`persistent_notification.create`、`alexa_devices.send_sound`
  和 `mqtt.publish` 各有自己的形式和目标，没有一个是 notify 动作。

notify 实体是正确的方向：它们可以按区域、标签和设备来指定目标，并能在界面中正确显示。但它们目前只能传递消息和标题，而且许多集成，
尤其是短信集成，还没有迁移过来。

## 通知动作的风格 { #the-styles-of-notification-action }

### 1. 针对服务的旧式 notify 动作 { #1-legacy-notify-action-for-a-service }

每个已配置的服务对应一个动作，形式相同：`message`、`title`、`target` 和自由格式的 `data`。`target` 的含义和 `data` 中的键
由各个集成决定。

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

Twilio SMS 的同一动作把电话号码作为 `target`，并在 `data` 中使用 `media_url`。

### 2. 针对设备的旧式 notify 动作 { #2-legacy-notify-action-for-a-device }

形式与风格 1 相同，但集成为每个设备创建一个动作，所以目标就在动作名里。主要例子是 Companion App，每部手机都有一个
`notify.mobile_app_<device>`，并且 iOS 和 Android 的 `data` 键不同。

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

### 3. 使用 `notify.send_message` 的 notify 实体 { #3-notify-entity-with-notifysend_message }

所有 notify 实体共用的一个动作，可以按实体、设备、区域或标签指定目标，并且界面编辑器完全支持。它只接受 `message` 和 `title`，
而且只有声明支持标题的实体才会使用标题。没有 `data`。

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. 集成自有的动作，以其 notify 实体为目标 { #4-the-integrations-own-action-aimed-at-its-notify-entity }

集成的 notify 实体用作目标，集成再添加一个自有动作，用扁平的字段承载 `notify.send_message` 无法发送的所有内容。每个集成的字段
都不同。

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

`smtp.send_message`、`html5.send_message`、`prowl.send_message`、`nfandroidtv.send_message` 以及 `telegram_bot.send_*`
系列动作也是同样的方式，只是各自字段不同。

### 5. 集成自有的动作，使用自己的目标 { #5-the-integrations-own-action-with-its-own-targets }

完全不基于 notify、按自己的方式选择目标的动作：一个设备、一个房间、一个主题，或者一个媒体播放器加一个 TTS 引擎。

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

其他还有 `lametric.message`(按 `device_id`)、`alexa_devices.send_sound`(按 `device_id`)、`matrix.send_message`
(按房间)、`mqtt.publish`(按主题)以及 `persistent_notification.create`(没有目标，显示在 Home Assistant 界面中)。

### 6. 组 { #6-groups }

两种 notify 组已在[上文](#why-cant-i-just-use-a-group)中介绍。Notify 组助手是配合风格 3 使用的 notify 实体。旧式 notify
组是一个风格 1 的动作，它会调用其他风格 1 或风格 2 的动作。

## 各集成及其风格 { #integrations-and-their-styles }

Home Assistant 2026.11。**两者皆有** 表示该集成有两种风格，其中 notify 实体是简单的那种，而超出消息和标题的内容需要另一种。

| 集成                    | 旧式动作 (1 或 2)                         | notify 实体 (3)                 | 自有动作 (4 或 5)                                 | 消息和标题之外                                     |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **两者皆有**，每部手机一个        | -                                                | 旧式 `data`：`image`、`actions`、`url` (iOS)、`clickAction` (Android)、`push` |
| SMTP (电子邮件)          | `notify.<name>`，`target` = 地址          | **两者皆有**，每个收件人一个       | `smtp.send_message` (4)                          | 旧式 `data.images`、`data.html`；自有动作 `html`、`attachments`、`priority` |
| Telegram 机器人          | 已在 2026.11 中移除                        | 有，每个聊天一个                  | `telegram_bot.send_message`、`send_photo`、... (4) | 自有动作：`keyboard`、`inline_keyboard`、`parse_mode`，照片和文件使用单独的动作 |
| Twilio SMS              | `notify.<name>`，`target` = 号码          | 无                              | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`，`target` = 号码          | 无                              | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`，`target` = 号码          | 无                              | -                                                | `data.attachments`、`data.urls`、`data.text_mode` |
| Pushover                | `notify.<name>`，`target` = 设备          | 无                              | -                                                | `data.priority`、`sound`、`url`、`attachment`、`html`、... |
| Slack                   | `notify.<name>`，`target` = 频道          | 无                              | -                                                | `data.blocks`、`data.file`                        |
| Discord                 | `notify.discord`，`target` = 频道 ID      | **两者皆有**，每个频道一个，无标题  | -                                                | 旧式 `data.images`、`data.embed`、`data.urls`      |
| Matrix                  | `notify.<name>`，`target` = 房间          | 无                              | `matrix.send_message` (5)                        | `data.images`                                     |
| HTML5 推送               | `notify.<name>`，`target` = 注册          | **两者皆有**                     | `html5.send_message` (4)                         | 自有动作：`image`、`icon`、`actions`、`urgency`、`ttl`、... |
| ntfy                    | -                                        | **两者皆有**                     | `ntfy.publish` (4)                               | 自有动作：`priority`、`tags`、`click`、`attach`、`actions`、... |
| Prowl                   | `notify.<name>`，已弃用                    | **两者皆有**，无标题              | `prowl.send_message` (4)                         | 自有动作：`priority`、`url`                        |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **两者皆有**                     | `nfandroidtv.send_message` (4)                   | 自有动作：`image`、`icon`、`duration`、`position`、... |
| LaMetric                | `notify.<name>`                          | **两者皆有**，无标题              | `lametric.message` 按设备 (5)                     | `icon`、`sound`、`cycles`、`priority`             |
| Kodi                    | `notify.<name>`                          | 无 (已提议)                      | -                                                | `data.icon`、`data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | 无                              | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **两者皆有**，每个设备有朗读和广播  | `alexa_devices.send_sound` 按设备 (5)            | 声音只能通过自有动作                                |
| 文字转语音 (TTS)         | `notify.<name>` (YAML `platform: tts`)   | 无                              | `tts.speak` (5)                                  | `media_player_entity_id`、`language`、`options`   |
| 持久通知                 | `notify.persistent_notification`         | 无                              | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | 有，无标题                        | `mqtt.publish` 按主题 (5)                         | 任意负载                                          |

## 通知人，而不是设备 { #notifying-a-person-not-a-device }

Home Assistant 知道每个人是谁、哪些设备追踪器在跟踪他们，却不知道怎样联系到他们。Home Assistant 团队正在解决这个问题，起因是社区的
“What the Heck?” 讨论 [Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879)，
并在[架构讨论 #1552](https://github.com/home-assistant/architecture/discussions/1552) 中提出了方案：每个人都有一份自己的
notify 实体列表，并且 `notify.send_message` 可以发送给 `person.anna`。这解决了日常最大的问题，即在每个自动化中更换手机，并让
notify 实体成为联系某人的自然方式。

一旦正式发布，Supernotify 将尽快支持这项功能：既可以通过一个人关联的 notify 实体向其发送，也可以让发给某人的
`notify.send_message` 经过 Supernotify 自己的路由。

## Supernotify 如何解决 { #what-supernotify-does-about-it }

Supernotify 接收一条通知和一组选项，并把它转换成适合每个渠道的调用：

- **一个动作搞定一切。** `supernotify.notify` 只需接收一次消息、标题、图片、按钮和优先级，每个
  [transport](../../transports/index.md) 会把其渠道支持的内容转换为该集成所需的风格、字段名和目标，无论是旧式动作、notify
  实体、自有动作还是 TTS。
- **面向人，而不是设备。** [Recipients](../../configuration/people.md) 保存每个人的电子邮件、电话号码、Telegram 聊天等信息，
  他们装有 Companion App 的手机会被自动发现。通知 `person.anna`，每个渠道都会得到正确的地址。每个 recipient 也有自己的
  notify 实体。
- **该发给谁。** 通知可以只发给在家的人，或只发给外出的人，也可以回退到其他渠道或其他人。请参阅配方
  [基于在场状态的路由与回退](../../recipes/presence_routing_with_fallback.md)。
- **关于什么。** [Scenarios](../../configuration/scenarios.md) 和优先级决定使用哪些渠道，因此低优先级的消息可以只发到手机，
  而紧急消息还会响起门铃提示音并通过扬声器播报。
- **不要太频繁。** [暂停提醒](../../usage/snoozing.md)和[重复检测](../../configuration/dupe_detection.md)可防止同一警报
  反复出现。
