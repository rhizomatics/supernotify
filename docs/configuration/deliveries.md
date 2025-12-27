---
tags:
  - delivery
  - condition
  - configuration
---
# Deliveries

*Delivery* is how the different available notifications are defined.

You should create a Delivery only for the [transports](../transports/index.md)
you want to use, though sometimes you may want to create multiple Deliveries for the same channel, for example a `plain_email` and `html_email` delivery, or different custom notification platforms using the `generic` transport.

Three of the transports will automatically create these deliveries where there is not an explicit delivery defined (if you really don't want a default delivery, set its transport `enabled` to `false`):

- `DEFAULT_email`
 - Only if there is an [SMTP Integration](https://www.home-assistant.io/integrations/smtp/) already configured ( it picks the first available one as the `action`, if you want another one then define the delivery explicitly)
- `DEFAULT_mobile_push`
- `DEFAULT_notify_entity`

```yaml title="Example of switching off a default delivery
transports:
  mobile_push:
    disabled: true
```

All other transport adaptors will not do anything unless there is a Delivery configured in the `delivery:` section of the Supernotify config.

## Simple Example

This example does 4 things:

1. Switches on SMS text messaging
2. Selects the `mikrotik_sms` integration as the SMS notify platform
3. Only switches on the delivery if everyone that is trackable is out of the house
4. Only switches on the delivery if notification priority is critical or high

If the conditions were more complex than this, a `condition` block could be applied.

```yaml title="Simple Example"
delivery:
    text_message:
        transport: sms
        action: notify.mikrotik_sms
        occupancy: only_out
        priority:
        - critical
        - high
```

## Other Reasons to Use

- Make sure critical notifications are heard. Fire up the sirens, push to mobile apps and send off email or SMS
- If you're paying for SMS, keep it only for critical notifications
- Adapt messaging style to occupancy
- Reduce notification noise by using sounds, like dings or bells, on chime devices or voice assistants

There are more examples in the [Recipes](../recipes/index.md) section.

## Simplifying Deliveries

There are two main ways:

- If you have multiple deliveries for the same Transport, then set common defaults at Transport level, using `delivery_defaults`
- Use [Scenarios](../usage/scenarios.md) to apply common chunks of config
- Move to a scenario-only configuration (recommended) by setting `selection` to `scenario` for every delivery
  - This makes Deliveries more of an opt-in model than opt-out, since all Deliveries are now inactive unless explicitly selected

In this snippet, all Delivery configurations for `alexa_devices` will use the defined target group.

```yaml title="Example Transport Defaults"
    alexa_devices:
      delivery_defaults:
        target:
          - group.alexa_announcements
```
## Overriding Message and Title

If your downstream transport has specific needs for the `message` and/or `title` then
these can be overridden or amended for only the deliveries that need them.

```yaml title="Override Message"
delivery:
  custom_notify:
    transport: generic
    action: notify.very_custom
    message: HOME ASSISTANT NOTIFICATION
```

For this delivery, whatever the `message` on the notification, it will be replaced by
"HOME ASSISTANT NOTIFICATION" when delivered to the custom notification.

!!! info
    `message` and `title` are the two special cases where the values in the configuration
    override the values in the Action `data`. For everything else the Action wins.

For amending rather than overriding, see the [Alexa Whisper Recipe](../recipes/alexa_whisper.md) for an example of using `message_template` in a [Scenario](../usage/scenarios.md).

## Controlling Targets

For fine-grained control over how any targets pre-defined in a delivery are treated, for example when explicit
targets provided in a notification action call, Delivery has an optional `target_usage` key, taking values of:

- `no_action` - Only uses the Delivery target if there's no target on the notification action call
- `no_delivery` - Only uses the Delivery target if there's no target applicable to this delivery
- `merge_delivery`- Combines the targets in the Delivery with any on the action call, only where delivery already has a target
- `merge_always` - Combines the targets in the Delivery with any on the action call, or if there's
  no target on the notification, it defaults to the Delivery target
- `fixed` - Only ever delivers to the targets in the Delivery config, ignoring any direct or indirect (for example `person_id`) in the action call

Additionally, `target_required` defines if this delivery needs targets to work, and should be skipped if no targets
are resolved as specific to it, for example based on the `target_categories` option to select by category. This has values:

- `always` - Targets are mandatory, skip this delivery if no targets identified for it
- `never` - Don't require targets, and don't even waste time computing them and don't supply them to the transport adaptor
- `optional` - Don't require targets but still compute them and make them available for the notification

## Delivery Selection

A list of `selection` options controls how deliveries are selected, each delivery can have multiple
options selected, though some of them are mutually impossible, like `default` and `explicit`

| Option              | Default | Usage                                                                                        |
|---------------------|---------|----------------------------------------------------------------------------------------------|
| `default`           | Y       | Use this delivery for every notification if there are targets and its not overridden         |
| `scenario`          | N       | Only use this delivery if a scenario enables it                                              |
| `explicit`          | N       | Doesn't do anything but can make your config easier to read than merely absence of `default` |
| `fallback`          | N       | Use this delivery only if no other delivery was selected                                     |
| `fallback_on_error` | N       | Use this delivery if no other delivery was successful and at least one of them had errors    |

## Entities

Deliveries are exposed as `sensor.supernotify_delivery_XXXX` entities in Home Assistant, with the configuration and
current state. They can be enabled or disabled like any other entities, for run-time control of notifications.

## Extreme Example

Its unlikely any Delivery would ever look quite like this, with every configuration key used. The full choice can also be found in the [Delivery Schema](../developer/schemas/Delivery_Definition.md) definition.

```yaml title="Complex Example"
delivery:
    all_bells_and_whistles:
        # Alias does nothing, just a place for longer name
        alias: Make a fuss if alarm armed or high priority
        # Which of the built-in transports to use
        transport: generic
        # This defaults to true, quick way to switch off all deliveries
        enabled: true
        # Which Home Assistant action (aka 'service') should be called
        action: script.my_alerter
        # These are fine-tuning options for the transport
        options:
            # only pass `entity_id` targets to the delivery
            target_categories:
              - entity_id
            # narrow down the entity ids selected
            target_include_re:
              - media_player\.chime_[A-Za-z0-9_]+
              - mqtt\.siren_[A-Za-z0-9_]+
            # don't deliver to a target already notified in this action
            unique_targets: true
        # bunch of data that only makes sense to the transport
        data:
            noise_level: scarey
            jitter: 23
        # standard targets to use
        target:
            entity_id:
                switch.hall_light
                switch.garage_buzzer
            person_id:
                person.joe_bob
        # use these targets always, whether or not the notification has explicit targets
        target_usage: merge_on_delivery
        # if there's no targets don't notify ( which always happen anyway because of the merge targets above )
        target_required: optional
        # Use this delivery only when explicitly selected by a scenario, or if all other deliveries fail with at least one error
        selection:
          - scenario
          - fallback_on_error
        # only deliver if notification is high or critical
        priority:
            - high
            - critical
        # only deliver if there's someone determined ( by mobile app tracker ) to be home
        occupancy: any_in
        # apply a further time and day of week condition
        conditions:
              alias: "Time 15~02"
              condition: time
              after: "15:00:00"
              before: "02:00:00"
              weekday:
                - mon
                - wed
                - fri
        # Send this delivery last ( this has affect on unique selection choice, so another delivery might hit a target first)
        selection_rank: last
        # fix the message and title, ignoring what's sent on notification
        message: ALERT!
        title: Overridden title
```
