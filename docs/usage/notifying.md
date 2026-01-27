---
tags:
  - example
  - action
  - automation
  - target
  - notification
description: How to send notifications using Supernotify from automations or the Home Assistant app
---
# Sending Notifications

From an automation, call Supernotify as you would any other `notify` platform. For many cases, you can convert an existing notification call to Supernotify by only changing the `action` name, for example if its an email notification, mobile push action or `notify.send_message`.

!!! info
    These examples assume you've named the Supernotify notifier as `supernotify` since that's simple and obvious, though
    you are free to name it however you like.

There are lots more examples in the [Recipes](../recipes/index.md), including how to make it work well
with Frigate, AppDaemon and Alexa.

## Simplest Example

In this example, there's no configuration, target or anything more than the standard `message`.

This notification will go out to all the implicit deliveries. If there's no configuration for Supernotify, then the default behaviour is to send a mobile push notification to all the devices for everyone with a `Person` entry in Home Assistant.

```yaml title="Example Message to All Devices"
  - action: notify.supernotify
    data:
        message: Something went off in the basement
```

## Adding Targets

Targets can be direct addresses, like an email address, telegram account or similar, or something indirect like a person. See [e-Mail](../configuration/email.md) for more on configuring e-mail notifications.

```yaml title="Example Message to All Devices"
  - action: notify.supernotify
    data:
        message: Something went off in the basement
        target: person.john_mcdoe
```

In this case, the notification will go only to John, to any mobile devices he's running Home Assistant on, and to any e-mail addresses that have been configured for him in Supernotify's `recipients` configuration.

Its also possible to put the e-mail, mobile action, notify entity or similar directly into the target:

```yaml title="Example Email Message"
  - action: notify.supernotify
    data:
        message: Something went off in the basement
        target: john@mcdoe.co.bn
```

Both these examples had a single target. The `target` field will work with a single value, a list of values, or a defined dictionary of values. Generally the dictionary isn't needed since Supernotify can take a big list and work out what belongs to which notification transport, though you may need it if doing custom notifications to Discord, Telegram or similar.

## Complex Targets

This is what a complicated target looks like - any of the separate address types can be a string or a list, whatever
is most convenient

```yaml
  - action: notify.supernotify
    data:
        message: Something went off in the basement
        target:
            email: john@mcdoe.co.bn
            phone_number: +4398708123987
            telegram: @bill
            mobile_app_id:
              - mobile_app.john_phone
              - mobile_app.john_ipad
```

## Controlling Delivery Selection

Delivery selection can be passed in the `data` of an action call, or implied from the
style in which the data presented. `delivery_selection` can be set to one of three values:

* `implicit` - The default
    - All deliveries are enabled plus scenario selected
    - This is implied if a dictionary mapping of deliveries is included
* `explicit` - Switch off delivery defaulting
    - Only deliveries listed on the action call are enabled, plus ones switched on by a scenario
    - This is switched on automatically if a list or single delivery is given.
* `fixed` - Switch off delivery defaulting and scenario delivery selection
    - Only the list of deliveries in the action call will be used, even if a scenario condition were to select another one
    - This is never implied or defaulted

## Using from an Automation

In this example, when an Actionable Notification is sent with action `Red Alert`, a notification
is triggered in Supernotify using the `red_alert` scenario. In this case, the scenario uses
sirens, chimes and Alexa noises to raise a ruckus so there's no need for `message` or `title`

```yaml
- id: action_red_alert
  alias: Action Red Alert
  initial_state: true
  triggers:
  - trigger: event
    event_type: ios.action_fired
    event_data:
      actionName: Red Alert
  action:
  - action: notify.supernotify
    data:
      data:
        scenario: red_alert
```

In this example, a mobile notification goes out to notify of the dishwasher finishing, and email is switched off.

```yaml
- id: '1762520266950'
  alias: Dishwasher Finished
  description: 'Push alert when dishwasher done'
  triggers:
  - trigger: state
    entity_id:
    - sensor.dishwasher_operation_state
    to:
    - finished
  actions:
  - action: notify.supernotify
    data:
      message: Dishwasher is finished
      data:
        delivery:
          plain_email:
            enabled:
```
### Automation and Templates

Templates can be used freely, as in other `notify` integrations

```yaml
- id: ups-overloaded
  alias: Send notification when UPS is overloaded
  triggers:
  - entity_id:
    - sensor.cyberpower_status
    to: Overloaded
    trigger: state
    for:
      hours: 0
      minutes: 0
      seconds: 30
  actions:
  - data:
      title: 'ALERT: UPS Overloaded'
      message: UPS is overloaded, output voltage {{states('sensor.cyberpower_output_voltage')}}
      data:
        priority: high
```

## Adding a Link to Mobile Push Notification

```yaml title="More Advanced Action Call"
  - action: notify.supernotify
    data:
        title: Security Notification
        message: Garden sensor triggered
        delivery:
            mobile_push:
                data:
                    clickAction: https://my.home.net/dashboard

```

Note here that the `clickAction` is defined only on the `mobile_push` delivery. However
it is also possible to simply define everything at the top level `data` section and let the individual
transport adaptors pick out the attributes they need. This is helpful either if you don't care about
fine tuning delivery configurations, or using existing notification blueprints, such as the popular
[Frigate Camera Notification Blueprints](https://github.com/SgtBatten/HA_blueprints/tree/6cffba9676ccfe58c5686bd96bf15a8237e1a3f9/Frigate_Camera_Notifications).


## References

The full range of things that go into the second level `data:` section is documented at
[Notify Action Data Schema](../developer/schemas/Notify_Action_Data.md)
