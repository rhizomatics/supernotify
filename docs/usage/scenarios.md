---
tags:
  - scenario
  - condition
description: Introduction to Scenarios in Supernotify for Home Assistant
---
# Scenarios

## What and Why

Scenarios can be defined both as a set of conditions which switch on the scenario and/or as a set of overrides to apply if the scenario is active.

For example, a scenario could be defined by conditions such as alarm panel arm state, occupancy and time to indicate when notifications should be minimized, and then different chime sounds could be selected or deliveries switched off.

Scenarios can override specific delivery configurations, general media configuration (such as setting a camera, or specifying which alert sound to use for a mobile push ) and disable implicit deliveries. Scenarios can be as small or as large as you want - it could define an entire set of deliveries, or patch a single value.

## Usage Modes

### Minor
* Couple of scenarios added to a minimal Supernotify configuration to redirect notifications based on occupancy, priority etc
### Medium
* Scenarios used to factor out common code from multiple `delivery` configs in Supernotify, or complicated automations, sequences, scripts, appdaemon apps etc.
### Major
* Fully scenario driven configuration
    * All `delivery` configurations have `selection: scenario` set so they are not enabled by default
    * Notifications that don't match a scenario get dropped
        * Alternatively, a fallback delivery can be selected if every message goes somewhere
    * This is a good option when you're comfortable with the integration and its configuration, and you have noisy notifications, which should be either dropped, or result only in a chime ringing or an Alexa sound playing.
    * Even if no notification occurs, there can still be an archive notification, to file system or MQTT as a record,
    for example if you are experimenting with tuning out noise, see [Archive](../configuration/archiving.md).

## Conditions

For more on the conditions, see the [ Home Assistant Conditions documentation](https://www.home-assistant.io/docs/scripts/conditions/) since the conditions are all evaluated at time of
notification by the standard Home Assistant module.

Supernotify also adds more context variables to use in conditions, see the full list on the [Condition Variables](../configuration/conditions.md#condition-variables) section. You can use these to switch on scenarios based on the notification priority, or even patterns of words in the message or title - see [Content Escalation Recipe](../recipes/content_escalation.md) for an example.


!!! tip
    There's a [Scenario Schema](../developer/schemas/Scenario_Definition.md) defined for the configuration,
    and [debugging hints](../configuration/conditions.md#debugging-conditions)



## Examples

This scenario could be used to select more obtrusive notifications, like email or Alexa announcements,
from a combination of conditions, hence simplifying separate notification calls, and providing
one place to tune multiple notifications.

```yaml
more_attention:
        alias: time to make more of a fuss
        conditions:
          condition: and
          conditions:
            - not:
                - condition: state
                  entity_id: alarm_control_panel.home_alarm_control
                  state: disarmed
            - condition: time
              after: "21:30:00"
              before: "06:30:00"
```

In this example, selecting the scenario by name in a notification call switches on
a set of delivery transports, which saves repetitive declaration in many notification calls. Delivery
Selection is made `implicit` so not switching off any other deliveries that would have applied.

```yaml
scenarios:
  red_alert:
      delivery:
        chime_red_alert:
        upstairs_siren:
        downstairs_siren:
      media:
        camera_entity_id: camera.porch
```

## Entities

Scenarios are exposed as `sensor.supernotify_scenario_XXXX` entities in Home Assistant, with the configuration and
current state as `unavailable` ( since their conditions are not continually being evaluated, only on demand). They can be enabled or disabled like any other entities, for run-time control of notifications.


## Overriding Delivery Selection and Configuration

Each delivery section within scenario has an `enabled` value, which defaults to `true`.

* `true` - This delivery will be enabled even if it is not an implicit delivery
* `false` - This delivery will be disabled, whether it is an implicit one, or selected by another scenario
* *Empty* - The delivery configuration will only be used to override the definition of a delivery that has already been selected, and if not, will be ignored when the scenario applied. Especially useful with [Wildcard Deliveries].

See the [Seasonal Greetings Recipe](../recipes/seasonal_greetings.md) for an example where the null value of `enabled`
is useful.

Lists and single values can also be used, if the only need is to switch on deliveries. These all do the same, so it is
kinder on everyone who sometimes gets their YAML styles mixed up.

```yaml title="Alternate Delivery Definition Styles"
scenarios:
  style_1:
    alias: Switch on email
    delivery:
      email:
  style_2:
    alias: Switch on email
    delivery:
      - email
  style_3:
    alias: Switch on email
    delivery: email
```

## Scenario Selection at Notification

Conditions aren't essential for scenarios, since they can also be switched on by a notification.

For example in this case, where the `home_security` and `garden` scenarios are explicitly
triggered, and so any overrides declared in those scenarios will be applied. The `constrain_scenarios`
prevents any scenario other than `unoccupied` or the ones explicitly applied here ( to switch off all
other scenarios, use `NULL`).

```yaml
  - action: notify.supernotifier
    data:
        title: Security Notification
        message: '{{state_attr(sensor,"friendly_name")}} triggered'
        priority: high
        apply_scenarios:
          - home_security
          - garden
        constrain_scenarios:
          - unoccupied
```

## Overriding Content

Individual deliveries can be overridden, including the content of the messages using `message_template` and `title_template`.
The templates are regular HomeAssistant `jinja2`, and have the same context variables available as the scenario conditions (see below ). In the example below, Alexa can be made to whisper easily without having to mess with the text of every notification, and this scenario could also have conditions applied, for example to all low priority messages at night.

```yaml
  scenarios:
    emotional:
      delivery:
        alexa:
          data:
            title_template: '<amazon:emotion name="excited" intensity="medium">{{notification_message}}</amazon:emotion>'
```

## Multiple Scenarios

Multiple scenarios can be applied, in the order provided, and each template will be applied in turn to the results of the previous template. So in the example below, you could apply both the *whisper* and *emotion* Amazon Alexa markup to the same message, or add in some sound effects based on any of the conditions.

A blank `message_template` or `title_template` can also be used to selectively switch off one of those fields for a particular delivery, for example when sending a notification out via email, push and Alexa announcement.

## Wildcard Deliveries

Delivery names can use regular expressions rather than literal names. For example, to suppress notifications by disabling all deliveries:

```yaml
scenarios:
  red_alert:
      .*:
       enabled: False
```

Any valid regular expression can be used, so for example if there are many "chime" deliveries:

```yaml
scenarios:
  red_alert:
      chime_.*:
       enabled: False
```

Regular expressions can be mixed and matched with literal delivery names, where there is a clash the
liternal name will work, where 2 regular expressions resolve to the same delivery, the last one to
be applied is used.

All deliveries are enabled by default - which makes regular scenarios easier to use - though can
mean that a wildcard switches on more deliveries than might be the intention. The solution for this is
to use an `enabled:` field, which won't force anything to be enabled.

For example, to override the priority for deliveries, without affecting deliveries that would otherwise not be selected.

```yaml
scenarios:
  red_alert:
      .*:
       enabled:
       data:
        priority: critical
```
