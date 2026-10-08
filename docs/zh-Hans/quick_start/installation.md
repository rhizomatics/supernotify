---
title: 安装
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: 通过 HACS 安装适用于 Home Assistant 的 Supernotify，并在界面中完成设置，无需 YAML
---

# 安装

## 通过 HACS 安装 { #install-from-hacs }

首先，确认已经安装 **HACS**。

如果还没有，请查看 [HACS 说明](https://hacs.xyz/docs/use/)。Supernotify 是 HACS 的默认仓库之一，因此不需要配置自定义仓库。

在 Home Assistant 的 HACS 页面中，从可用集成列表里选择 **Supernotify**，下载它，然后重启 Home Assistant。

![在 HACS 中选择](../../assets/images/hacs_select.png){width=400}

## 添加集成 { #add-the-integration }

进入 **设置 → 设备与服务 → 添加集成**，搜索 **Supernotify**。接受默认值即可。

![添加集成](../../assets/images/new_integration.png)

## 自动发现与默认值 { #discovery-and-defaults }

要让通知开始工作，只需要做以上这些。

Supernotify 会查看 Home Assistant 中已有的内容，并找到：

- **人员** - Home Assistant 中每个拥有 *人员* 或 *用户* 的人，以及他们运行 Home Assistant 应用的手机或平板
- **通知方式** - 移动推送、已有的 SMTP 电子邮件集成、所有 notify 实体，以及 Alexa 音箱或门铃之类的设备（如果有的话）

它会为找到的每种通知方式创建一个 *delivery*；如果你有相应的设备，还会创建一些便捷的 delivery，例如 `chime_siren_all` 和 `alexa_devices_announce_all`。

归档、重复检测和日常清理的设置，之后可以在集成的 **配置** 选项中调整。

现在[发送第一条通知](first_notification.md)。
