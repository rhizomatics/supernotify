---
tags:
  - scenario
  - recipe
  - autoarm
  - alarm_control_panel
  - mobile_actions
  - actionable_notifications
  - autoarm
description: Select the mobile actions to appear on notifications based on alarm arm state
---
# Recipe - Contextual Mobile Actions

## Purpose

When mobile actions are included in an *Actionable Notification*, only include ones that are currently
relevant. So if the Alarm Control Panel is disarmed, don't show the *Disarm* action, and likewise if
the panel is armed.

This avoids the mobile notification being messy and cluttered, and also the inevitable incorrect
selections by the inhabitants.

## Implementation

Uses a **Scenario**, with conditions to select the alarm control panel states, and `action_groups` to
pick pre-defined sets of mobile actions. The *Arm* action will only show if alarm panel state is disarmed,
and the *Reset* action will always be available.

This scenario contributes only mobile actions, and other scenarios ( or delivery defaults ) could combine
to contribute other things like sirens, camera snapshots, push noises etc.

The mobile action itself will be handled by the [AutoArm](https://autoarm.rhizomatics.org.uk) custom
integration, which responds to the `ALARM_PANEL_DISARM`, `ALARM_PANEL_RESET` etc action keys.

## Example Configuration

```yaml
name: SuperNotifier
platform: supernotify
recipients:
  - person: person.joe_mcphee
    mobile_devices:
        - mobile_app_id: mobile_app_joe_nokia

delivery:
  apple_push:
    transport: mobile_push
scenarios:
  alarm_disarmed:
    conditions:
      - condition: state
        entity_id: alarm_control_panel.home_alarm
        state:
          - disarmed
    action_groups:
      - alarm_panel_arm
      - alarm_panel_reset

  alarm_armed:
    conditions:
    - condition: state
      entity_id: alarm_control_panel.home_alarm
      state:
        - armed_home
        - armed_night
        - armed_away
    action_groups:
      - alarm_panel_disarm
      - alarm_panel_reset

action_groups:
  alarm_panel_disarm:
    - action: ALARM_PANEL_DISARM
      title: "Disarm Alarm Panel"
      icon: "sfsymbols:bell.slash"
  alarm_panel_reset:
    - action: ALARM_PANEL_RESET
      title: "Arm Alarm Panel for at Home"
      icon: "sfsymbols:bell"
  alarm_panel_arm:
    - action: ALARM_PANEL_AWAY
      title: "Arm Alarm Panel for Going Away"
      icon: "sfsymbols:airplane"
```

### Example Notify Action

```yaml
action: notify.supernotify
data:
    message: Motion detected in hallway
```

## Variations

The occupancy and time of day could also be taken into account, so for example the *Armed Night* action
wasn't offered during the day.
