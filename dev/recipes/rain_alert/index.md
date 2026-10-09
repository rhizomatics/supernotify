# Recipe - Rain Alert

Source: https://supernotify.rhizomatics.org.uk/latest/recipes/rain_alert/

## Purpose

Get a quiet reminder on the phone while it's raining, repeated every hour until it stops, using Home Assistant's [Alert](https://www.home-assistant.io/integrations/alert/) integration.

## Implementation

An alert only gives a notifier a message and a title, so what kind of notification it becomes is set in a scenario. The scenario has a `notify_entity`, which gives it a `notify.its_raining_again` entity, and an action of the same name for the alert to list in its `notifiers`. See [Scenario Notify Entity](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/#notify-entity).

Everything the alert sends has the scenario applied, which makes the mobile push low priority and gives it a rain icon. Low priority is passed on to an iPhone as a `passive` notification, which doesn't light up the screen or make a sound.

## Example Configuration

supernotify.yaml

```yaml
scenarios:
  rain:
    alias: Its raining again
    notify_entity: its_raining_again
    delivery:
      mobile_push:
        data:
          priority: low
          notification_icon: mdi:weather-pouring
```

configuration.yaml

```yaml
alert:
  rain:
    name: Its raining again
    entity_id: binary_sensor.rain
    repeat: 60
    notifiers:
      - its_raining_again
```

`mobile_push` is the standard delivery Supernotify makes when there are phones with the Home Assistant app, so there's nothing more to configure for it.

## Variations

- Add `done_message` to the alert to be told when the rain has stopped, which goes through the same scenario.
- Add more deliveries to the scenario, such as a chime.
- The same notify entity works anywhere else that takes one, like an automation's `notify.send_message`.
