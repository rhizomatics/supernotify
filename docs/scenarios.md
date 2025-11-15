# Scenarios

Scenarios can be defined both as a set of conditions which switch on the scenario and/or as
a set of overrides to apply if the scenario is active.

For example, a scenario could be defined by conditions such as alarm panel arm state, occupancy
and time to indicate when notifications should be minimized, and then different chime sounds
could be selected or deliveries switched off.

Scenarios can override specific delivery configurations, general media configuration (such as setting a camera, or specifying which alert sound to use for a mobile push ). A scenario has a
default `delivery_selection` basis of `implicit`, where the scenario inherits all the default
deliveries, or have this switched off by overriding `delivery_selection` to `explicit` in which case only the deliveries mentioned in the scenario are included.

For more on the conditions, see the [ Home Assistant Conditions documentation](https://www.home-assistant.io/docs/scripts/conditions/) since the conditions are all evaluated at time of
notification by the standard Home Assistant module. Supernotify also adds more context variables to
use in conditions, see the full list on the [Condition Variables](index.md#condition-variables) section.

!!! tip
  There's a [Scenario Schema](developer/schemas/Scenario%20Definition/) defined.

### Example Scenarios

This scenario could be used to select more obtrusive notifications, like email or Alexa announcements,
from a combination of conditions, hence simplifying separate notification calls, and providing
one place to tune multiple notifications.

```yaml
more_attention:
        alias: time to make more of a fuss
        condition:
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
red_alert:
      delivery_selection: implicit
      delivery:
        chime_red_alert:
        upstairs_siren:
        downstairs_siren:
      media:
        camera_entity_id: camera.porch
```

Delivery selection can also be passed in the `data` of an action call, as one of `explicit`,
`implicit` or `fixed`, the latter disables scenarios from enabling or disabling deliveries and leaves it solely
to defaults or what's listed in the action call. `implicit` is the default, and `explicit` can also
be switched on automatically if a list or single delivery is provided.

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

Multiple scenarios can be applied, in the order provided, and each template will be applied in turn to the results of the previous template. So in the example below, you could apply both the *whisper* and *emotion* Amazon Alexa markup to the same message, or add in some sound effects based on any of the conditions.

A blank `message_template` or `title_template` can also be used to selectively switch off one of those fields for a particular delivery, for example when sending a notification out via email, push and Alexa announcement.
