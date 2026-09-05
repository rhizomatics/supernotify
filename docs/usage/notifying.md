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

## Notification Priority

Use the `priority` key in `data` to set an optional priority. This can be used within Supernotify to switch on or off deliveries or scenarios ( for example a siren to accompany 'critical' notifications).

It will also be mapped to delivery priority flags where the underlying transport allows, for example Mobile Push, Gotify, Ntfy, SMTP, Telegram.

Valid Priorities:

- critical
- high
- medium
- minimum

Example Message

```yaml
  - action: notify.supernotify
    data:
        message: Something boring happened
        priority: low
```

## Duplicate Notifications

Notifications are checked for duplicates based on a selected policy. This
can also be turned off for individual notifications using `force_resend`.

```yaml
  - action: notify.supernotify
    data:
        message: Something happened
        force_resend: true
```

See [Duplicate Configuration](../configuration/dupe_detection.md) for more information.

## Controlling Delivery Selection

Delivery selection can be passed in the `data` of an action call using the `delivery_selection` key, or implied from the *shape* of the `delivery:` key itself. It can be set to one of three values:

* `implicit` - The default
    - All deliveries whose own `selection` includes `default` are enabled, plus any switched on by an active scenario
    - This is implied if `delivery:` is a dictionary mapping, or is left out entirely
* `explicit` - Switch off delivery defaulting
    - Only deliveries listed on the action call are enabled, *plus* ones switched on by a scenario
    - This is implied automatically if `delivery:` is given as a list or a single value
* `fixed` - Switch off delivery defaulting and scenario delivery selection
    - Only the list of deliveries in the action call will be used, even if a scenario condition were to select another one
    - Deliveries with `priority` or `condition` filtering will have this overridden - only a disabled `delivery`/`transport` stops a fixed selection
    - This is never implied from `delivery:`'s shape - it must always be set explicitly

An explicit `delivery_selection` always wins over whatever the shape of `delivery:` would otherwise imply - it's a default, not an override. If in doubt, add the `delivery_selection` to make it clear.

```yaml title="Implicit (default) - implied by a mapping"
  - action: notify.supernotify
    data:
        message: Garden sensor triggered
        delivery:
            mobile_push: # tunes an existing (default or scenario) delivery
              data:
                clickAction: https://my.home.net/dashboard
```

In this example, `mobile_push` and `plain_email` are selected as deliveries, even if they are not default ones. In addition
any deliveries selected by conditions or scenarios will be added to the list.

```yaml title="Explicit - implied by a list"
  - action: notify.supernotify
    data:
        message: Garden sensor triggered
        delivery:
            - mobile_push
            - plain_email
```

In this case `plain_email` will be chosen even if the delivery `condition` or `priority` is not met, or the delivery is explicit or scenario only, and other deliveries will be switched off. You get just the fixed list you asked for:

```yaml title="Fixed - always set explicitly"
  - action: notify.supernotify
    data:
        message: Garden sensor triggered
        delivery_selection: fixed
        delivery:
            - plain_email
```

!!! info "Two different things are both called `selection`"
    `delivery_selection` here is a per-*action-call* choice of how deliveries get resolved for
    this one notification. It's a different mechanism from a delivery's own config-time
    `selection` list (`default` / `scenario` / `explicit` / `fallback` / `fallback_on_error` -
    see [Delivery Selection](../configuration/deliveries.md#delivery-selection)), which decides
    whether that delivery is a candidate for implicit selection at all. The two happen to share
    the word "explicit" for unrelated things - `delivery_selection: explicit` is about the action
    call; a delivery with `selection: [explicit]` is excluded from implicit selection, as does
    any other value other than `default` (or left unstated, which is equivalent to `default`).

### When Scenarios Disagree

Each scenario can set a delivery's `enabled` to `true`, `false`, or leave it empty - see
[Overriding Delivery Selection and Configuration](scenarios.md#overriding-delivery-selection-and-configuration).

If more than one scenario is active at once and they disagree on the same delivery, **`false`
always wins**, regardless of how many other active scenarios enabled it - there's no priority
or ordering between scenarios.

The only way to override a scenario's `false` is for the action
call itself to explicitly re-enable that delivery in its own `delivery:` data. This is a
deliberate fail-safe default (a scenario that says "don't send this" is never silently
overruled by another scenario), but it also means there's currently no way for a scenario
author to mark their `enabled: true` as one that should win a conflict.

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

## Customizing message per channel

```yaml title="Channel Specific Messages"
  - action: notify.supernotify
    data:
        message: Garden sensor triggered
        title: Something has happened
        delivery:
            plain_email: # only effects the delivery called `plain_email`
              data:
                message: Garden sensor was triggered
            sms: # refers to a transport, so effects all deliveries based on SMS transport
                message: Garden Activity
                title: HASS
```

## A Better UI - `supernotify.notify`

Everything above uses `notify.supernotify`, so it fits in with any other `notify` platform and existing notification blueprints. The same options are also available as `supernotify.notify` - options that would otherwise be buried in the generic `data:` field (`priority`, `delivery`, `require_scenarios`, `media`, and so on) are instead top-level fields, each with its own selector in the Tools Actions or Automations editor UI, and validated against
[its own schema](../developer/schemas/Notify_Action.md).

```yaml title="Same Example, via supernotify.notify"
  - action: supernotify.notify
    data:
        message: Garden sensor triggered
        priority: high
        delivery: [mobile_push, plain_email]
```

`supernotify.notify` also propagates the calling action's `Context` through to deliveries - `notify.supernotify` can't do this, since it's routed through Home Assistant's legacy `notify`
platform, which doesn't pass on the `Context` it receives (see the note under "Tracing Activities" in the [changelog](../changelog.md)).

## References

The full range of things that go into the second level `data:` section is documented at [Notify Action Data Schema](../developer/schemas/Notify_Action_Data.md)
