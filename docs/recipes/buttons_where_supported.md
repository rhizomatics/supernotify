---
tags:
  - scenario
  - recipe
  - condition
  - mobile_push
  - pushover
  - actionable_notifications
title: Send Notifications with Action Buttons Only Where They Work
description: Use a Supernotify Scenario to send notifications with action buttons to the Companion App instead of a transport that can't show them, like Pushover
---
# Recipe - Send Buttons Only Where They Work

## Purpose

Use Pushover for everyday notifications, but send any notification with action buttons to the Home Assistant Companion App instead, since Pushover can't show buttons.

Supernotify picks deliveries by target, not by what the notification contains, so on its own a notification with buttons still goes to Pushover, with the buttons left out. A delivery's `fallback:` doesn't help either, as that is only used when a delivery fails.

## Implementation

A **Scenario** with a condition on the `notification_actions` and `notification_action_groups` [condition variables](../configuration/conditions.md#condition-variables), which hold the `actions` and `action_groups` given on the notify action. When either has something in it, the scenario switches Pushover off and Mobile Push on.

## Example Configuration

```yaml
delivery:
  pushover:
    transport: pushover
    inclusion: default
  mobile_push:
    transport: mobile_push
    inclusion: scenario

scenarios:
  needs_buttons:
    alias: Buttons only work on the Companion App
    conditions: "{{ (notification_actions + notification_action_groups) | length > 0 }}"
    delivery:
      pushover:
        enabled: false
      mobile_push:

action_groups:
  garage:
    - action: CLOSE_GARAGE
      title: Close the garage
```

Either of these notifications goes to the Companion App, and one without `actions` or `action_groups` goes to Pushover:

```yaml
action: notify.supernotify
data:
  message: Garage door left open
  action_groups:
    - garage
```

```yaml
action: notify.supernotify
data:
  message: Garage door left open
  actions:
    - action: CLOSE_GARAGE
      title: Close it now
```

## Notes

- Action groups added by a scenario aren't in `notification_action_groups`, since scenarios add them after their conditions are checked. Only what's given on the notify action is there.
- Buttons put directly in a Companion App style `data: actions:` aren't in `notification_actions`, but can be checked with `notification_data.actions`.
- To send to both, leave out the `pushover: enabled: false` part.
