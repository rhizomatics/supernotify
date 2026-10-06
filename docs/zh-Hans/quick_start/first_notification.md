---
title: 发送第一条通知
tags:
  - quickstart
  - developer tools
  - notification
description: 从 Home Assistant 发送第一条 Supernotify 通知 - 发给所有人、发给一个人，以及发到 Alexa 音箱
---
# 发送第一条通知

本页的所有操作都在 Home Assistant 界面中完成，紧接在[安装](installation.md)之后。每一步也给出了 YAML，供偏好 YAML 的人使用。

## 1. 通知所有人 { #1-notify-everyone }

打开 **开发者工具** 中的[动作选项卡](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab)，选择 `supernotify.notify` 动作，输入一条消息，然后按 **执行动作**。

![开发者工具中的动作](../../assets/images/tools_action_notify.png){width=600}

```yaml title="发给所有人的消息"
action: supernotify.notify
data:
  message: Something went off in the basement
```

一条通知只需要一条消息。不指定其他内容时，它会发送到家中每个人运行 Home Assistant 应用的所有手机和平板。

## 2. 通知一个人 { #2-notify-one-person }

这多半比你想通知的人要多。要缩小范围，可以选择 `person` 实体，或单独的移动设备，作为**目标**（target）：

![通知一个人的所有移动设备](../../assets/images/person_notify.png){width=400}

```yaml title="发给一个人的消息"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

现在只有 John 的设备会收到。选择人而不是手机，意味着 John 换了新手机之后通知仍然能送达。

## 3. 选择发送方式 { #3-choose-how-its-sent }

**Delivery** 框列出了 Supernotify 找到的通知发送方式。不填时由 Supernotify 替你选择；从中选择后，就只使用选中的那些。

![选择 delivery](../../assets/images/delivery_choice.png)

如果你有 Alexa 设备，可以使用 `alexa_devices_announce_all` 或 `alexa_devices_speak_all`。（announce 会先播放一声提示音，speak 则没有。）它们可以与电子邮件和移动应用通知组合在同一条通知中。

```yaml title="音箱和手机一起"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

每种方式都会收到适合它的通知：音箱把消息念出来，手机把消息显示出来。

这一步成功之后，接下来就是[把通知添加到自动化中](next_steps.md#add-a-notification-to-an-automation)。
