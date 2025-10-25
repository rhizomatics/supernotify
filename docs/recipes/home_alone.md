# Recipe - Home Alone

## Purpose

Vary how and which notifications are made if someone is home on their own.

## Implementation

Uses a **Scenario** and the automatic occupancy checks that are enabled using mobile discovery
when `recipients` are defined in the config. [AutoArm](https://jeyrb.github.io/hass_autoarm/) or
custom automations set the *Alarm Control Panel* state to night.

## Example Configuration

```yaml
recipients:
    - person: person.joe_mcphee
      email: joe.mcphee@home.mail.net
      phone_number: "+3294924848"
    - person: person.jabilee_sokata
      email: jab@sokata.family.net
scenarios:
    lone_night:
        alias: only one person home at night
        condition:
            condition: and
            conditions:
            - "{{notification_priority not in ['critical','high','low']}}"
            - "{{'LONE_HOME' in occupancy}}"
            - condition: state
                entity_id: alarm_control_panel.home_alarm_control
                state:
                - armed_night
        action_groups:
            - alarm_panel
            - lights
        delivery:
            apple_push:
            alexa_announce:
            plain_email:
            chimes:
```

## Variations

- Determine night time using the `sun` entity, or a daylight sensor device, rather than alarm status.
- Check for 2 or more people at home
    ```yaml
    "{{'ALL_HOME' in occupancy or 'MULTI_HOME' in occupancy}}"
    ```
