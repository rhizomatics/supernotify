# Core Classes

```mermaid
classDiagram

  Notification "1" *-- "*" Envelope
  Notification "1" *-- "1" ConditionVariables
  Envelope "1" ..> "1" DeliveryMethod
  Context "1" o-- "0..*" Scenario
  Context "1" o-- "0..*" Snooze
  Context "1" *-- "1" Snoozer
```

::: custom_components.supernotify.delivery_method.DeliveryMethod
    handler: python
    heading_level: 2


::: custom_components.supernotify.notification.Notification
    handler: python
    heading_level: 2


::: custom_components.supernotify.envelope.Envelope
    handler: python
    heading_level: 2


::: custom_components.supernotify.scenario.Scenario
    handler: python
    heading_level: 2

::: custom_components.supernotify.snoozer.Snooze
    handler: python
    heading_level: 2

::: custom_components.supernotify.ConditionVariables
    handler: python
    heading_level: 2
