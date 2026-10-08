---
title: 接下来做什么
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: 发出第一条 Supernotify 通知之后可以做什么 - 从自动化发送通知、添加仪表盘、选择通知谁和通知什么，并在配方中寻找灵感
---
# 接下来做什么

先从自动化开始，因为通知就是为它而生的。其余内容都是可选的，可以按任意顺序进行。

## 把通知添加到自动化中 { #add-a-notification-to-an-automation }

`supernotify.notify` 和其他动作一样，可以按通常的方式放进自动化。下面的例子在走廊的人体传感器被触发时发送一条通知。

创建一个以人体传感器为触发器的自动化，然后选择 **添加动作** 并搜索 Supernotify：

![选择动作](../../assets/images/add_action_automation.png){width=600}

填写消息，以及你想从[第一条通知](first_notification.md)中沿用的其他内容，例如目标或 delivery：

![配置动作](../../assets/images/automation_action_simple.png){width=600}

```yaml title="人体传感器自动化"
alias: Hallway motion notification
triggers:
  - trigger: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
actions:
  - action: supernotify.notify
    data:
      title: Motion detected
      message: Something is moving in the hallway
      target: person.john_mcdoe
```

如果还想在音箱上听到，请把 `alexa_devices_announce_all` 和 `mobile_push` 添加为 delivery。[发送通知](../../usage/notifying.md)介绍了这个动作能做的其他所有事情。

想看一个更完整的实例，包含语音播报和摄像头画面，请参阅配方[有人在门口](../../recipes/someone_at_the_door.md)。

## 添加仪表盘 { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) 提供了许多专用的仪表盘卡片，用于控制和监视通知、手动发送通知或测试配置。

![概览卡片和 transport 卡片](../../assets/images/cards.png)

[Dashboard](../../configuration/dashboard.md) 页面有一个完整的示例，可以粘贴到新的仪表盘中，之后就能以可视化方式编辑。

## 开启和关闭人员与 delivery { #switch-people-and-deliveries-on-and-off }

Supernotify 知道的每个人在 Home Assistant 中都有一个 `switch` 实体，每个 delivery 也是如此。关闭其中一个，就可以让某人不被打扰，或让音箱安静一会儿，而不用修改任何自动化。

## 只通知部分设备 { #notify-just-some-devices }

除了人或设备，目标还可以是**区域**、**楼层**或**标签**，因此通知可以只发到楼下的音箱，或发到所有带厨房标签的设备。请参阅 [Targets](../../usage/targets.md)，常见问题见 [FAQ](../../faqs.md)。

## 调整设置 { #tune-the-settings }

归档、重复检测和日常清理可以在 **设置 → 设备与服务** 中，通过集成的 **配置** 选项修改。请参阅[归档](../../configuration/archiving.md)和[重复检测](../../configuration/dupe_detection.md)。

## 寻找灵感 { #be-inspired }

[配方](../../recipes/index.md)中有许多带示例配置的点子。

## 用 YAML 更进一步 { #go-further-with-yaml }

加上一些 YAML 配置可以做到更多，而且这些全都是可选的：

- 为人员添加电子邮件地址或电话号码，见 [People](../../configuration/people.md)
- 创建你自己的 delivery，例如 HTML 电子邮件或一组固定的音箱，见 [Deliveries](../../configuration/deliveries.md)
- 用 [Scenarios](../../configuration/scenarios.md) 改变通知在夜间或家中无人时的行为
- 附加摄像头快照，见 [Multimedia](../../configuration/multimedia.md)

[进阶概念](advanced_concepts.md)解释了这些功能背后的思路，[配置](../../configuration/index.md)则是参考文档。

## 获取帮助 { #get-help }

可以在 [Discussions](https://github.com/rhizomatics/supernotify/discussions) 页面提问，或使用 AI 助手 - 参见 [FAQ](../../faqs.md) 中的最后一个回答。
