---
tags:
  - people
  - recipe
  - scenario
  - condition
  - occupancy
title: Home Alone - Tuned Notifications
description: Change which notifications are sent, and how they're sent, based on how many people in the house
---
# Recipe - Home Alone

## Purpose

Vary how and which notifications are made if someone is home on their own.

## Implementation

Uses a **Scenario** and the automatic occupancy checks that are enabled using mobile discovery when the *Person* integration is used in Home Assistant and automatically discovered in Supernotify. [Auto Arm](https://autoarm.rhizomatics.org.uk/) or custom automations set the *Alarm Control Panel* state to night.

## Example Configuration

```yaml
scenarios:
    lone_night:
        alias: only one person home at night
        conditions:
            condition: and
            conditions:
            - "{{notification_priority not in ['critical','high','low']}}"
            - "{{'LONE_HOME' in occupancy}}"
            - condition: state
              entity_id: alarm_control_panel.home_alarm_control
              state:
              - armed_night
        delivery:
            - mobile_push
            - alexa_devices_announce_all
            - email
            - chimes
```

## Variations

- Add email addresses, phone numbers, telegram IDs etc to Recipients in the Supernotify configuration screen to give more ways to contact people
- Determine night time using the `sun` entity, or a daylight sensor device, rather than alarm status.
- Check for 2 or more people at home
    ```yaml
    "{{'ALL_HOME' in occupancy or 'MULTI_HOME' in occupancy}}"
    ```
