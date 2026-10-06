---
title: 移除
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: 移除适用于 Home Assistant 的 Supernotify，并清理残留内容
---

# 移除 Supernotify

在 HACS 菜单中选择 `Supernotify`，然后在 `...` 菜单中选择 `移除`。

### 清理配置 { #cleaning-up-config }

1. `config` 目录中手动创建的 YAML 文件不会被改动；如果确定以后不再需要，请手动删除。
2. 已归档的通知会保留下来，除非另行配置，默认位于 `/config/archive/supernotify` 目录。需要时请删除该目录。
3. 如果使用了摄像头或图片附件，可能会留下媒体文件，除非另行配置，默认位于 `/config/media/supernotify` 目录。需要时请删除该目录。
4. 可能会留下模板，除非另行配置，默认位于 Home Assistant 配置目录下的 `supernotify/templates` 目录。需要时请删除该目录。
