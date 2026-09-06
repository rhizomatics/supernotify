![Supernotify](../assets/images/dark_icon.png){ align=left }

# Supernotify

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)

 <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=rhizomatics&repository=supernotify" target="_blank" rel="noopener noreferrer">
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="添加到 HACS">
   </a>
<br/>
<br/>
<br/>

**Home Assistant 统一通知系统**

### 重大变更 v2.0.0

>> SuperNotify 的 `2.0.0` 版本迁移到了原生的 Home Assistant UI 配置方式（"ConfigFlow"）。如果你已经使用简单配置，系统会自动为你完成迁移，无需任何 YAML。

>> 如果你使用的是高级配置（推送、场景、摄像头、人员、操作等），系统会发起一个*修复*，将这些内容迁移到新的 `supernotify.yaml` 文件中，并在你的 `configuration.yaml` 中添加一条 `include` 语句。你也可以选择按自己喜欢的方式，手动将配置从 `notify` 块中移出。

>> 无论哪种方式，都不会删除或注释掉任何内容，因此很容易撤销此更改。当你确认新版本对你可以正常工作后，再删除旧配置。这也会从日志中移除来自旧版 notify 实现的 `[homeassistant.components.notify] Failed to initialize notification service supernotify` 警告。

基于 Home Assistant 内置 `notify` 平台构建的**统一通知接口**，大幅简化多通知渠道和复杂场景的管理——包括多渠道通知、条件通知、移动操作、摄像头快照、门铃音效和基于模板的 HTML 邮件。

Supernotify 只有一个目标——**用最简单的通知触发尽可能多的推送，无需编写代码，配置最少**。

这让自动化、脚本和 AppDaemon 应用保持简洁易维护，所有细节和规则集中在一处管理。最简单的通知——只有一条消息——就足以触发所需的一切。在一处修改邮件地址，Supernotify 自动判断使用哪些移动应用。

仅通过 UI 配置，即可向家中所有人发送移动推送通知，无需配置移动应用名称。

![通知操作示例](../assets/images/notification.png){width=500}

## 分发方式

Supernotify 是通过 [Home Assistant 社区商店](https://hacs.xyz)（**HACS**）提供的自定义组件。基于 [Apache 2.0 许可证](https://www.apache.org/licenses/LICENSE-2.0)，免费开源。

## 文档

请查阅[快速入门](https://supernotify.rhizomatics.org.uk/getting_started/)、[核心概念](https://supernotify.rhizomatics.org.uk/concepts/)说明以及可用的[传输适配器](https://supernotify.rhizomatics.org.uk/transports/)。[发送通知](https://supernotify.rhizomatics.org.uk/usage/notifying/)介绍了如何从自动化或开发者工具操作页面调用 Supernotify。

还有许多包含示例配置的[使用示例](https://supernotify.rhizomatics.org.uk/recipes/)，也可按[标签](https://supernotify.rhizomatics.org.uk/tags/)浏览。


## 功能特性

* 一个操作 -> 多条通知
    * 消除自动化中的重复配置和代码
    * 适配器自动为每个集成调整通知数据
    * 例如，配合 [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) 通过邮件接收摄像头快照
* 自动配置
    * 移动推送、邮件（SMTP）和通知实体的推送配置自动完成
    * 自动发现移动应用，包括手机厂商和型号信息
    * 自动发现用于门铃音效的 Alexa 设备
* 超越 `notify` 集成
    * 门铃音效、警报器、短信、TTS、Alexa 广播与音效、API 调用、MQTT 设备
    * 支持所有标准 `notify` 和 `notify.group` 实现
    * 大幅简化移动推送通知的使用，例如 iPhone
* 条件通知
    * 使用 Home Assistant 标准 `conditions`
    * 添加了额外条件变量，包括消息内容和优先级
    * 结合在家检测，根据人员在家情况、消息优先级和内容灵活调整通知
* **场景**功能，实现简洁配置
    * 将常用配置和条件逻辑打包复用
    * 按需应用（`red_alert`、`nerdy`）或根据条件自动触发
* 统一人员模型
    * 定义邮件、短信号码或移动设备，然后在通知操作中使用 `person` 实体
    * 人员连同其移动应用自动配置
* 简便的 **HTML 邮件模板**
    * 标准 Home Assistant Jinja2，可在 YAML 配置、操作调用或独立文件中定义
    * 内置默认通用模板
* **移动操作**
    * 为多条通知设置一套统一的移动操作
    * 包含按条件静音的*稍后提醒*操作
* 灵活的**图片快照**
    * 支持摄像头、MQTT 图片和图片 URL
    * 支持在快照前后将摄像头移动到 PTZ 预设位置
* 配置级别选择
    * 可在传输适配器、推送和操作级别设置默认值
* **重复通知**抑制
    * 可调整重新允许前的等待时长
* 通知**归档**与**调试支持**
    * 可选将通知归档到文件系统和/或 MQTT 主题
    * 包含完整的调试信息
    * 推送、传输、收件人和场景在 Home Assistant 界面中作为实体公开


## 仅高级用途需要 YAML

Supernotify 目前支持使用标准 Home Assistant UI 进行基本设置配置，并支持[基于 YAML 的配置](https://supernotify.rhizomatics.org.uk/configuration/yaml/)以实现高级功能。保留 YAML 是为了便于处理更大的规则集。

使用简单的非 YAML 配置即可完成很多操作，包括移动推送设置的自动化。请参阅文档中的[使用示例](recipes/index.md)，以及以下移动推送示例：

```yaml title="零 YAML，全部通过 UI 配置"
  - action: supernotify.notify
    data:
        message: 你好！这是 Supernotify 的测试，正在向所有人的移动应用发送通知
```


##  面向 Home Assistant 的 Rhizomatics 开源项目

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - 使用物理按钮、在家状态、日历等自动布防/撤防 Home Assistant 警报控制面板
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - 适用于 Home Assistant 的 OpenTelemetry（OTLP）和 Syslog 事件采集


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - 通过文件系统将 ANPR/ALPR 车牌摄像头与 MQTT 集成
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Docker 镜像更新时通过 MQTT 自动通知

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
