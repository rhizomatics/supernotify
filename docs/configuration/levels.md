---
tags:
  - configuration
  - yaml
---
# Configuration Levels

## Flexible Configuration

Delivery configuration can be done in lots of different ways to suit different configurations and to keep those configuration as minimal as possible.

Each delivery can be individually configured, or have defaults provided by a `transport` configuration. A limited
set of overrides - `target`,`data`,`enabled` - can then be applied by scenarios, people definitions in `recipients` or in the notification call. (The limited set is to keep both the code and configuration from being so flexible its too complicated to work with.)

| Where                       | Where        | Schema                                                                   | Notes                                                |
|-----------------------------|--------------|--------------------------------------------------------------------------|------------------------------------------------------|
| Action Data                 | Runtime call | [Delivery Customization](../developer/schemas/Delivery_Customization.md) | Only `target`,`enabled` and `data` can be overridden |
| Recipient delivery override | Runtime call | [Delivery Customization](../developer/schemas/Delivery_Customization.md) | Only `target`,`enabled` and `data` can be overridden |
| Scenario delivery override  | Runtime call  | [Delivery Customization](../developer/schemas/Delivery_Customization.md) | Multiple scenarios applied in no special order. Only `target`,`enabled` and `data` can be overridden. `enabled` can also be left empty so scenario only applies to deliveries already selected. `enabled: true` will force the delivery on and `enabled: false` will force it off, whether an implicit delivery or selected by another scenario |
| Delivery definition         | Configuration | [Delivery](../developer/schemas/Delivery_Definition.md)                  | `message` and `title` are the exceptions which override Action Data                                   |
| Transport Delivery Defaults        | Configuration         |  [Transport Delivery Defaults](../developer/schemas/Transport_Definition.md#property-transport-definition-enabled)                                              |
| Transport Adaptor Defaults        | Code         |  - |                                            |
| Underlying action defaults        | Other Integrations | - | These are configured outside Supernotify       |


For example, if there's one specific automation you didn't want to have your `alexa_announce` delivery applied, you could disable it like this rather than adding more rules to the supernotify config for just one case:

```yaml
  - action: notify.supernotify
    data:
        title: For Your Eyes Only
        message: There might be someone in the house!!!
        delivery:
            alexa_announce:
                enabled: false
```

## Priority order of configuration application

1. Action Data passed at runtime call
2. Recipient delivery override
3. Scenario delivery override
4. Delivery definition
5. Transport defaults
6. Target notification action defaults, e.g. mail recipients ( this isn't applied inside Supernotify )
