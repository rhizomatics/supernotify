---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Home Assistant 的 Supernotify 核心概念，包括 Transport、Delivery、Scenario 和 Recipient
---
# 核心概念

## 整体如何协作 { #how-it-fits-together }

来自自动化的一条通知，可以变成多条不同的通知，每一条都根据发送方式进行调整。

![一条来自自动化的通知变成一封电子邮件、两条推送提醒、一条短信和一次音箱播报](../assets/images/concepts_flow.svg)

1. **目标** - 根据 [Recipient](#recipient) 信息，把人转换为可以联系到他们的方式
2. **Deliveries** - 选出适用的 [Deliveries](#delivery)，可以是默认的，也可以通过 [Scenarios](#scenario) 选择
3. **通知** - 每个 delivery 取出它能使用的目标，并发送适合它的通知，
   这样电子邮件可以使用带图片的完整 HTML 版式，而厨房音箱则收到一段简短的语音消息

## 目标 (Target) { #target }
- 通知谁或什么，以及如何通知
  - *直接*目标
    - 电子邮件地址
    - 电话号码
    - `entity_id` 或 `device_id`，例如通过 Alexa 设备进行播报
    - 用于 Telegram 等专用 transport 的自定义 ID
  - *间接*目标，可以转换为直接目标
    - `person_id`，用于使用 *Recipient* 功能
    - Home Assistant 标准目标选择器 `label_id`、`floor_id` 和 `area_id`
    - *群组*目标（Home Assistant 新旧两种群组）
- 目标可以指定特定的**目标类别**，例如 `discord_channel:839439434`，详见[类别前缀](../usage/targets.md#category-prefixes)
- 每个目标都由最适合处理它的集成从列表中取出
  - 例如，Alexa Devices 的 Notify 实体由 Alexa Devices transport 处理，而普通的 Notify 实体则回退到功能较少的 Notify Entity transport
- 更多信息请参阅 [Targets](../usage/targets.md)

## 接收人 (Recipient) { #recipient }
- 一个人，可选择包含电子邮件地址、电话号码、移动设备或自定义目标
  - 默认会从 Home Assistant 中已有的用户账户和人员实体自动发现
- 这样在自动化中指代某人更方便：使用 `person.joe_mctest`，而不必在每条通知里记住 Joe 的电子邮件地址。如果安装了兼容的短信集成，也适用于电话号码，还支持 Telegram 或 Discord 等自定义标识
- 每个接收人还有一个 Home Assistant `switch` 实体，可以轻松让某人不再受通知打扰
- 更多详情请参阅 [People](../configuration/people.md) 和 [Recipes](../recipes/index.md)

## 传输 (Transport) { #transport }

- *Transport* 是实际发送通知的技术手段，通常使用已安装的某个 Home Assistant 集成
- *Transport 适配器*正是普通 Notify 群组与 Supernotify 的区别所在
  - Notify 群组看似可以轻松实现多渠道通知，但实际上每个 transport 的 `data` 结构（还有 `data` 里的 `data`！）、寻址方式等都不同，最终只能把通知简化为最少的共同属性，比如只有 `message`！
- Supernotify 自带常见 transport 的适配器，如电子邮件、移动推送、短信和 Alexa，还有一个 *Generic* 适配器，可以封装任何其他 Home Assistant 动作
- Transport 适配器可以把一条通知发送到多个平台，即使它们的接口各不相同、互不兼容
- 它会根据 transport 调整通知：去掉不支持的属性，重组 `data` 结构，只选择合适的目标，并在可能时允许进一步微调
- 每个 transport 都有默认配置，可以做大量微调并设置默认值，无需在每条通知中重复相同的值
- 更多详情请参阅 [Transports](../transports/index.md)

## 投递 (Delivery) { #delivery }

- **Delivery** 定义你想使用的每个通知渠道
  - 开箱即用时，每个 transport 都有一个同名的 delivery，例如 `email` 或 `mobile_push`
  - 某些 transport 会自动创建额外的 delivery，例如 `alexa_devices_announce_all` 或 `chime_siren_all`
  - 通过 YAML 可以创建更多 delivery，例如在纯文本 `email` 之外再加一个 `html_email`，或为特定语音助手创建不同的 delivery
- 能够明确选择目标的 transport，如电子邮件、移动推送、短信、Alexa Devices 和 Notify Entity，默认会参与目标处理
  - 其他 transport 可以通过配置、使用 Scenarios 或在通知中请求来加入
- 你可以用自己选择的名称定义 delivery，并为同一个 transport 设置多个 delivery，例如 `plain_email` 和 `html_email`
- [Generic Transport](../transports/generic.md) 就像一个*工具箱*，可以为 Home Assistant 能做、但标准 transport 尚未覆盖的几乎任何事情创建 delivery
- 更多详情请参阅 [Deliveries](../configuration/deliveries.md) 和 [Recipes](../recipes/index.md)

## 场景 (Scenario) { #scenario }
- 一组设置，可以按名称启用，也可以根据 Home Assistant 条件自动启用
- Scenarios 可以通过通知 `data` 块中的 `apply_scenarios` 值手动选择，也可以通过标准的 Home Assistant `conditions` 块自动选择
  - 条件可以包含消息文本，因此 Frigate 关于露台上有鸟的通知，可以与窗边有可疑人员的通知区别处理
- 使用 scenarios 可以让通知在夜间更低调、在节日更喜庆，或优先处理某些消息
- 它们让你可以在一个地方对许多 delivery 或通知统一应用更改，是大幅简化自动化中通知调用的关键
- 更多详情请参阅 [Scenarios](../configuration/scenarios.md) 和 [Recipes](../recipes/index.md)

## 优先级 (Priority) { #priority }
- 通知的紧急程度
   - 无论在 Home Assistant 内外，都没有统一的通知优先级标准
   - Supernotify 有自己的 5 级方案，遵循最常见的做法，从 `minimum` 到 `critical`
   - 优先级可用于 scenario 和 delivery 规则，也可以传递给支持它的通知集成
   - Supernotify 有自己的电子邮件集成，会把优先级转换为 Outlook、Apple Mail 等能理解的形式

!!! info
    对技术细节感兴趣的读者，可以查看与这些概念对应的核心类的[类图](../developer/class_diagram.md)。

# 核心原则 { #core-principles }

1. 一条通知只需要一条消息，其他一切都可以使用默认值，包括所有目标
2. 在动作调用中定义的内容优先于默认值
   - 可以通过 `target_usage` 等选项进行调整
   - 只有在没有指定目标时，才会使用人员注册表生成目标
3. 配置和默认值的优先级为：Action > Scenario > Delivery > Transport
4. 在配置和调用方式上尽量宽松
   - 目标可以按子类别组织，也可以是实体 ID、设备 ID、电子邮件和电话号码组成的一个大列表
   - 动作 `data` 中的选项（如 `delivery`）可以是单个值、列表或字典映射

## 开发者 { #developers }

有关通知如何流经 deliveries、目标和 *Envelopes*，请参阅 [Developer Concepts](../developer/concepts.md)，另请参阅 [Design Principles](../developer/design/principles.md)。
