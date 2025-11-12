# People


While Home Assistant has both a `Person` and `User`, neither are directly useful or extensible for notifications.

Supernotify adds a **People Registry** for notifications, which builds on top of the Home Assistant entities ( and
will be retired when Home Assistant does have this support).

With the person definition you can:

- Define an email address just once, and then refer to the target as `person.joe_soap` in notification calls
- Likewise for phone numbers, for SMS, and for mobile devices
  - For mobile apps, its much easier to switch on the automatic discovery, and let the People Registry find them
- Also register custom targets, like Discord, Telegram etc IDs, that could be used in a *Generic* delivery
- Set default targets for specific deliveries, so for example, an email address is always copied in on them


This means you can do multi-channel notification with a single reference to a `person` entity in a notification,
and automatically the email, phone number, mobile app notification service, or whatever else is used as appropriate
in each notification.

Since by default everyone in the people list gets every notification, you don't even need to define targets at all in
each automation/script/blueprint/appdaemon app.

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
