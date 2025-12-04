---
tags:
  - alexa
  - recipe
  - echo
  - condition
description: Use an alternative Amazon Alexa integration in case the main one is having issues
---
# Recipe - Alexa Alternative Integration

## Purpose

When *Alexa Devices* integration stops working, have an alternative, here *Alexa Media Player* ready to be quickly enabled.

## Implementation

Define both deliveries and use the `enabled` status on transport to select which one active ( or enable/disable dynamically
by changing the entity in Home Assistant between `on` and `off`).

This means that scenarios, or automations sending notifications, can refer to both Alexa integrations, and the broken one can quickly be switched off centrally and the alternative enabled.

## Example Configuration

```yaml
delivery:
 alexa_backup_announce:
      transport: alexa_media_player
      occupancy: any_in
      selection: scenario
      enabled: false

    alexa_announce:
      transport: alexa_devices
      occupancy: any_in
      selection: scenario
      enabled: true
      target:
        - notify.bedroom_announce
        - notify.kitchen_alexa_announce
        - notify.living_room_flex_announce
        - notify.studio_announce

scenarios:
    normal_day:
      alias: Ordinary notifications
      condition:
        condition: and
        conditions:
          - "{{notification_priority not in ['critical','high','low']}}"
      delivery:
        apple_push:
        alexa_announce:
        alexa_backup_announce:
```
