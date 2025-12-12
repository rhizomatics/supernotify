---
tags:
  - mobile_push
  - email
  - sms
  - people
  - recipients
  - occupancy
---
# People

While Home Assistant has both a `Person` and `User`, neither are directly useful or extensible for notifications
and occupancy checks.

Supernotify adds a **People Registry** for notifications and occupancy, which builds on top of the Home Assistant
entities ( and will be retired/adapted when Home Assistant does have this support). The term *Recipient* is used for what Supernotify manages, to distinguish from the Home Assistant terms.

With the `recipient` definition you can:

- Define an email address just once, and then refer to the target as `person.joe_soap` in notification calls
  - The person entity_id will automatically be replaced by the e-mail address for deliveries that take e-mail
- Likewise for phone numbers, for SMS, and for mobile devices
  - For mobile apps, with **automatic discovery**, the People Registry finds them for you, no config needed
- Also register custom targets, like Discord, Telegram etc IDs, that could be used in a *Generic* delivery
- Switch off a recipient, even if they were automatically discovered
- Set default targets for specific deliveries, so for example, an email address is always copied in on them

## Automatic Recipient Discovery

The registry is automatically populated from all *Person* entities defined in HomeAssistant, unless you switch this off using `recipient_discovery: false` in the configuration. And sice each *Recipient* is automatically populated with all their mobile devices, an empty YAML config can do a lot.

``` yaml title="Disabling One of the Automatic Discoveries"
 recipients:
    - person: person.new_home_owner
      enabled: false
```

## Automatic Mobile App Discovery

By default, all the mobile devices registered in Home Assistant are discovered and associated with the recipient.

This can be switched off by default for everyone:

```yaml
 notify:
  - name: minimal
    platform: supernotify
    mobile_discovery: false
```

or per recipient:

``` yaml
 recipients:
    - person: person.new_home_owner
      mobile_discovery: false
```

It is also possible to have discovery off by default at platform level, then selectively re-enabled for
the folk you want, using the `recipients` configuration.

If you want to do the device registration manually, see [Manual Device Registration](#manual-device-registration)

## Sending Notifications

This means you can do multi-channel notification with a single reference to a `person` entity in a notification,
and automatically the email, phone number, mobile app notification service, or whatever else is used as appropriate
in each notification. This is all it takes:

```yaml title="Example Message to All Devices"
  - action: notify.supernotify
    data:
        title: Security Notification
        message: Something went off in the basement
```

Since by default everyone in the people list gets every notification, you don't even need to define targets at all in
each automation/script/blueprint/appdaemon app.

If you want to pin it down to specific people, add a list of targets ( you can also mix and match this
target list with email addresses, notify entities, or direct mobile actions ).

```yaml title="Example Message to Some People"
  - action: notify.supernotify
    data:
        title: Warning All Kids
        message: Something happened and we are unhappy
        target:
         - person.johnny_mctest
         - person.jeanie_mctest
         - person.jolly_mctest

```
## Entities

Recipients are exposed to Home Assistant as `supernotify.recipient_XXXXX` entities. The entity state is
the recipient `enabled` flag, and changing the entity in Home Assistant ( by main UI, Developer Tools,
automations, API or whatever ) will disable or enable the recipient.

This can be handy if someone should be temporarily switched off for notifications, or you want your own
automation to determine which people get notified when.

The entity also exposes the recipient attributes, such as email, mobile devices, target, custom data etc.

## Manual Configuration

``` yaml title="Simple Example"
 recipients:
    - person: person.new_home_owner
      email: jalaboli@myhome.net
      phone_number: "+430504103451"
      delivery:
        alexa_announce:
        target:
            - media_player.echo_study
```

## Manual Device Registration

``` yaml title="Complicated Example"
 recipients:
    - person: person.new_home_owner
      alias: sysadmin
      email: jalaboli@myhome.net
      phone_number: "+430504103451"
      delivery:
        mobile_push:
        target:
            - mobile_app.new_iphone
        data:
            push:
            sound:
                name: default
        alexa_announce:
        target:
            - media_player.echo_study
    - person: person.bidey_in
      phone_number: "+4287600013834"
      target:
        - switch.garden_shed_chime
      mobile_discovery: false
      mobile_devices:
        - manufacturer: nokia
        model: 6110
        mobile_app_id: mobile_old
        device_tracker: device_tracker.nokia_6110
      delivery:
        text_message:
        enabled: false
```

## References

- [Person Integration](https://www.home-assistant.io/integrations/person/)
