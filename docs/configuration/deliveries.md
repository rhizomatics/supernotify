---
tags:
  - delivery
  - condition
---
# Deliveries

*Delivery* is how the different available notifications are defined.

You should create a Delivery only for the [transports](../transports/index.md)
you want to use, though sometimes you may want to create multiple Deliveries for the same channel, for example a `plain_email`
and `html_email` delivery, or different custom notification platforms using the `generic` transport.

With the exception of *Notify Entity*, none of the transport adaptors will do anything unless there is a Delivery configured in the `delivery:` section of the Supernotify config. (And if you really don't want a default Notify Entity delivery, set its transport `enabled` to `false`).

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

- If you have multiple deliveries for the same Transport, then set common defaults at Transport level, using
`delivery_defaults`
- Use [Scenarios](../scenarios.md) to apply common chunks of config
- Move to a scenario-only configuration (recommended) by setting `selection` to `scenario` for every delivery
  - This makes Deliveries more of an opt-in model than opt-out, since all Deliveries are now inactive unless explicitly selected

In this snippet, all Delivery configurations for `alexa_devices` will use the defined target group.

```yaml title="Example Transport Defaults"
    alexa_devices:
      delivery_defaults:
        target:
          - group.alexa_announcements
```

## Extreme Example

Its unlikely any Delivery would ever look quite like this, with every configuration key used. The full
choice can also be found in the [Delivery Schema](../developer/schemas/Delivery_Definition.md) definition.

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
        condition:
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
