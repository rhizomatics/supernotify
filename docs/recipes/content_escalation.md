# Recipe - Content Escalation

## Purpose

Make a notification more impactful if the message or titl has certain words in it.

## Implementation

Uses a **Scenario** and ability of standard templating to see and make logic checks on the notification message.

In this case a Frigate notification is usually a medium priority, however if the phrase `person was detected` is in the message, and the alarm state indicates the house is empty, these are sent as text message, email and mobile push just to make sure it gets through.

## Example Configuration

```yaml
  scenarios:
    high_alert:
        alias: make a fuss if alarm armed or high priority
        condition:
          condition: and
          conditions:
            - "{{notification_priority not in ['critical','low']}}"
            - condition: or
              conditions:
                - "{{notification_priority in ['high'] and 'person was detected' in notification_message|lower }}"
                - condition: state
                  entity_id: alarm_control_panel.home_alarm_control
                  state:
                    - armed_away
                    - armed_vacation
        delivery:
          plain_email:
          sms:
          apple_push:
        action_groups:
          - alarm_panel
          - lights
```

## Variations

- Use ```{{'LONE_HOME' in occupancy}}``` to check if home is empty
