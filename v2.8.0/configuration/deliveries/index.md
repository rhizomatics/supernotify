# Deliveries

*Delivery* is a pre-set configuration for a specific *Transport* - it controls the configuration and can set values that would otherwise have to be repeated in every notification.

The simplest case though is that you never know or worry about them - if you add an email address as a target for a notification, the email delivery is used, or a phone number for SMS, and if you add a big list of random targets, Supernotify will work out the right delivery for each. See [Targets](https://supernotify.rhizomatics.org.uk/latest/usage/targets/index.md) for more information.

If you need, Deliveries can be manually selected on a notification, for example sending some to Telegram and others to email, or having a siren fire also for some. They can also be automatically selected using conditions or Scenarios.

## Standard Delivery

A Delivery gets configured automatically for every usable [transport](https://supernotify.rhizomatics.org.uk/latest/transports/index.md), it will check the underlying integration, like Ntfy or Telegram, has been set up in Home Assistant, and if it needs entities like Media Players, whether these exist.

For example, if there is an [SMTP Integration](https://www.home-assistant.io/integrations/smtp/) an `email` Delivery will be set up, with the SMTP `action`.

These standard deliveries will default to explicit inclusion (you have to list them in the `delivery` key of the notification ), with the exception below.

Some transports, `email`, `mobile_push`, `alexa_devices` and `sms` can reasonably be expected to always notify if configured, and have the ability to pick their targets (an email address is obviously an email address). So the standard delivery for these will be a `default` inclusion, which means even if a notification has nothing more defined than a `message` it will be sent out to via these delivery channels. If, however, there are also custom deliveries for these transports, the standard delivery will stand down to `explicit`, to avoid duplicate notifications.

In any case, the `inclusion` key can be used, either in the Transport or Delivery configuration, to override any of the automatic choices. See [Delivery Inclusion](#delivery-inclusion) for more on how that works.

## Customizing Delivery

You may want to create multiple Deliveries for the same channel, for example a `plain_email` and `html_email` delivery, or different custom notification platforms using the `generic` transport. Be careful to have constraints, like priority, occupancy or conditions, if there are multiple deliveries so you don't get duplicate notifications.

Or more simply, you can customize the standard delivery created for each transport, here's an example, which refines the standard `sms` delivery, created because the home already has a working SMS integration, and switches on the delivery only if notification priority is critical or high

If the conditions were more complex than this, a `condition` block could be applied.

Customizing Standard Delivery

```yaml
delivery:
    sms: # same name as transport
        priority:
        - critical
        - high
```

If the name `text_message` had been chosen here, then there would now be two deliveries, `sms` ( the automatic standard one ) and `text_message` (my new custom one) defined.

If you only have one delivery, this is the same thing as:

Customizing Standard Delivery

```yaml
transports:
    sms:
      delivery_defaults:
        occupancy: only_out
        priority:
        - critical
        - high
```

## Other Reasons to Use Delivery

- Make sure critical notifications are heard. Fire up the sirens, push to mobile apps and send off email or SMS
- If you're paying for SMS, keep it only for critical notifications
- Adapt messaging style to occupancy
- Reduce notification noise by using sounds, like dings or bells, on chime devices or voice assistants

There are more examples in the [Recipes](https://supernotify.rhizomatics.org.uk/latest/recipes/index.md) section.

## Simplifying Deliveries

- If you only have one delivery config, don't bother with the `delivery:` config, just update the `delivery_defaults` for the transport, so the standard delivery is set up the way you like it
- If you have multiple deliveries for the same Transport, then set common defaults at Transport level, using `delivery_defaults`
- Use [Scenarios](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/index.md) to apply common chunks of config
- Move to a scenario-only configuration (recommended) by setting `inclusion` to `scenario` (or `explicit`, these do the same thing) for every delivery
- This makes Deliveries more of an opt-in model than opt-out, since all Deliveries are now inactive unless explicitly selected

In this snippet, all Delivery configurations for `alexa_devices` will use the defined target group.

Example Transport Defaults

```yaml
    alexa_devices:
      delivery_defaults:
        target:
          - group.alexa_announcements
```

## Overriding Message and Title

If your downstream transport has specific needs for the `message` and/or `title` then these can be overridden or amended for only the deliveries that need them.

Override Message

```yaml
delivery:
  custom_notify:
    transport: generic
    action: notify.very_custom
    message: HOME ASSISTANT NOTIFICATION
```

For this delivery, whatever the `message` on the notification, it will be replaced by "HOME ASSISTANT NOTIFICATION" when delivered to the custom notification.

Info

`message` and `title` are the two special cases where the values in the configuration override the values in the Action `data`. For everything else the Action wins.

For amending rather than overriding, see the [Alexa Whisper Recipe](https://supernotify.rhizomatics.org.uk/latest/recipes/alexa_whisper/index.md) for an example of using `message_template` in a [Scenario](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/index.md).

## Controlling Targets

For fine-grained control over how any targets pre-defined in a delivery are treated, for example when explicit targets provided in a notification action call, Delivery has an optional `target_usage` key, taking values of:

- `no_action` - Only uses the Delivery target if there's no target on the notification action call
- `no_delivery` - Only uses the Delivery target if there's no target applicable to this delivery
- `merge_delivery`- Combines the targets in the Delivery with any on the action call, only where delivery already has a target
- `merge_always` - Combines the targets in the Delivery with any on the action call, or if there's no target on the notification, it defaults to the Delivery target
- `fixed` - Only ever delivers to the targets in the Delivery config, ignoring any direct or indirect (for example `person_id`) in the action call

Additionally, `target_required` defines if this delivery needs targets to work, and should be skipped if no targets are resolved as specific to it, for example based on the `target_categories` option to select by category. This has values:

- `always` - Targets are mandatory, skip this delivery if no targets identified for it
- `never` - Don't require targets, and don't even waste time computing them and don't supply them to the transport adaptor
- `optional` - Don't require targets but still compute them and make them available for the notification

See [Targets](https://supernotify.rhizomatics.org.uk/latest/usage/targets/index.md) for more info on how to use them.

## Delivery Inclusion

A list of `inclusion` options controls how deliveries are included, each delivery can have multiple options included, though some of them are mutually impossible, like `default` and `explicit`

| Option              | Default | Usage                                                                                        |
| ------------------- | ------- | -------------------------------------------------------------------------------------------- |
| `default`           | Y       | Use this delivery for every notification if there are targets and its not overridden         |
| `scenario`          | N       | Only use this delivery if a scenario enables it                                              |
| `explicit`          | N       | Doesn't do anything but can make your config easier to read than merely absence of `default` |
| `fallback`          | N       | Use this delivery only if no other delivery was selected                                     |
| `fallback_on_error` | N       | Use this delivery if no other delivery was successful and at least one of them had errors    |

Info

`inclusion` replaces the deprecated `selection` key (same values, same meaning) - existing config using `selection` still works but should be migrated.

Info

This is a config-time property of the delivery itself - whether it's a *candidate* for implicit inclusion at all. For the separate, per-notification `delivery_selection` choice (`implicit`/`explicit`/`fixed`) made on an action call, see [Controlling Delivery Selection](https://supernotify.rhizomatics.org.uk/latest/usage/notifying/#controlling-delivery-selection).

## Entities

Each delivery has a `switch.supernotify_delivery_XXXX` entity, on the **SuperNotify** device, that is the delivery `enabled` flag, with the delivery configuration as attributes. Turning it off ( by main UI, Developer Tools, automations, API or whatever ) disables the delivery, and turning it on enables it again, for run-time control of notifications. Each transport also has a switch, `switch.supernotify_transport_XXXX`, which allows all deliveries for that transport to be quickly disabled, without changing the delivery switches themselves. Only a transport that is loaded, and so usable, has a switch, as do only its deliveries. A switch left from a transport or delivery that is no longer loaded shows as unavailable, and can be deleted from its entity settings.

Switching a delivery or transport on or off lasts across restarts and reloads, see [Overrides](#overrides).

Deprecated

The delivery and transport `binary_sensor.supernotify_delivery_XXXX` and `binary_sensor.supernotify_transport_XXXX` entities are kept only for backward compatibility, and will be removed in a future version. They are read-only, mirroring the switches: writing their state no longer enables or disables anything. They are not created on a new install, and a repair is raised once in Home Assistant if you have one enabled.

### Overrides

Switching a scenario, recipient, delivery or transport on or off with its switch overrides its configured `enabled` value. The override lasts across restarts and reloads, while its configured value - its own `enabled`, or for a delivery without one, its transport's - is unchanged. Changing that value in the configuration, and reloading, puts it back as configured. So does the `supernotify.reset_overrides` action, for everything or for one kind at a time.

- A scenario without conditions is driven by its *Scenario Manual* `binary_sensor`. That on/off state is not an override of the configuration, so `supernotify.reset_overrides` leaves it as it is, and only puts the scenario's switch back.
- An override belongs to its switch entity. While the switch is disabled in Home Assistant, its override is not applied and the configured value is used, and `supernotify.reset_overrides` can't clear it. Enabling the switch again brings the override back - turn it back with the switch, or use `supernotify.reset_overrides` once the switch is enabled again.
- A delivery with no `enabled` of its own follows its transport's configured `enabled`, so changing the transport's `enabled` in the configuration also ends that delivery's override.
- The override is saved by Home Assistant's own restore state mechanism, so it lasts as long as the switch exists: it's forgotten if the switch has been missing for about 7 days, and, as Home Assistant saves it every 15 minutes and on a clean shutdown, a change up to 15 minutes before a crash can be lost.

## Removing

Its also possible to completely switch off transports, so that they don't show up anywhere in Home Assistant, and there's no Delivery option, and no ability to dynamically switch them back on.

Example of switching off a transport completely

```yaml
transports:
  mobile_push:
    load: false
```

## Extreme Example

Its unlikely any Delivery would ever look quite like this, with every configuration key used. The full choice can also be found in the [Delivery Schema](https://supernotify.rhizomatics.org.uk/latest/developer/schemas/Delivery_Definition/index.md) definition.

Complex Example

```yaml
delivery:
    all_bells_and_whistles:
        # Alias does nothing, just a place for longer name
        alias: Make a fuss if alarm armed or high priority
        # Which of the built-in transports to use
        transport: generic
        # This defaults to true, quick way to switch off this delivery
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
        target_usage: merge_always
        # if there's no targets don't notify ( which always happen anyway because of the merge targets above )
        target_required: optional
        # Use this delivery only when explicitly selected by a scenario, or if all other deliveries fail with at least one error
        inclusion:
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
