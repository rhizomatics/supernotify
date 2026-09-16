---
tags:
  - ios
  - android
  - live
  - mobile_push
title: Use Live Activities to Track Dishwasher Cycle
description: Use the Live Activity feature introduced in Home Assistant 2026.7 to keep an in progress live notification on a mobile device
---
# Recipe - Live Activities to Track Dishwasher

In this example, there's a Bosch dishwasher using Home Direct, though it can be easily adapted for any appliance by changing the sensor name and possibly the operating state name.

The automations are defined in YAML here but can be added easily via the Automations UI, or copy/pasted in.

## Cycle Started

```yaml title="Home Assistant Automation"
alias: Dishwasher started
triggers:
  - trigger: state
    entity_id:
      - sensor.dishwasher_operation_state
    to:
      - run
actions:
  - action: supernotify.notify
    data:
      message: Dishwasher Started
      title: Dishwasher
      delivery_selection: fixed
      delivery:
        - mobile_push
        - alexa_devices_annnounce_all
      data:
        tag: dishwasher
        live_update: true
        notification_icon: mdi:dishwasher
```

## Cycle Ended

```yaml title="Home Assistant Automation"
alias: Dishwasher Finished
triggers:
  - trigger: state
    entity_id:
      - sensor.dishwasher_operation_state
    to:
      - finished
actions:
  - action: supernotify.notify
    metadata: {}
    data:
      title: Dishwasher
      message: Dishwasher is finished
      delivery_selection: fixed
      delivery:
        mobile_push:
          data:
            message: clear_notification
        alexa_devices_announce_all:
      data:
        tag: dishwasher
        live_update: true
        notification_icon: mdi:dishwasher

```

### Variations

Use the `progress` or `chronometer` to track progress more precisely. Track specific phases, like 'pre-wash` if your appliance exposes it.

Re-apply for washing machines, ovens or other smart appliances.
