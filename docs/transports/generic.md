---
tags:
  - transport
  - generic
  - script
  - rest_command
  - light
  - siren
  - mqtt
  - input_text
  - switch
  - notify
  - custom
---
# Generic Transport Adaptor

| Transport ID | Source                                                                                                                                    | Requirements | Optional                                                    |
|--------------|-------------------------------------------------------------------------------------------------------------------------------------------|--------------|-------------------------------------------------------------|
| `generic`    | :material-github:[`generic.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/generic.py) | -            | *Any Home Assistant action from core or custom integration* |

Use to call any actiom, including 'legacy' Notification action (previously known in Home Assistant as 'service' ), that is one not using the newer `NotifyEntity` model. It can be used for simple calls,
or as a "toolbox" for more complex needs.

### Notify Actions

If an action is in then `notify` domain, then `message`,`title`,`target` and `data` will be
passed in the Action (Service) Data.

```yaml title="Example Configuration"
delivery:
  chat_notify:
    transport: generic
    action: notify.custom_chat
```

Use this deliveries with action calls like this:

```yaml title="Example Action Call"
    - action: notify.supernotify
      data:
        title: "My Home Notification"
        message: "Notify via custom chat"
        delivery:
            chat_notify:
                data:
                    channel: 3456
```

This includes support for [MQTT Notify Entities](https://www.home-assistant.io/integrations/notify.mqtt/). (Supernotify also offers an [MQTT Transport Adaptor](mqtt.md) for direct flexible access to `mqtt.publish`.)

### Selecting Targets

By default, Generic will throw all the targets applied in the configuration or action call at the notification, in one flat list
of targets, or a single string value if only one target.

Usually you will want to be more specific. If the target is a common built-in type like `entity_id` or `email`, then specify this in the `target_categories` option.

```yaml
delivery:
  chat_notify:
    transport: generic
    action: notify.custom_chat
    options:
      target_categories: entity_id
```

If it's not a standard target type, then make one up. In this example, for personal Slack channels, which
in this example is called "slack_channel" but can be anything you like so long as it matches up ( you could
have separate categories for "slack_group_dm", "slack_user" etc)

```yaml title="Config Snippets"
recipients:
  - person: person.my_user
    delivery:
      slack:
        target:
           slack_channel: A20H2AN55DX
delivery:
  slack:
      transport: generic
      action: notify.my_slack_service
      options:
           target_categories: slack_channel
```

This can also be used in a notification call:

```yaml title="Example Action Call"
    - action: notify.supernotify
      data:
        message: "Notify via slack"
        target:
            slack_channel: #JH838434
```

### Known Integrations

Generic isn't completely a blank slate - it knows about the most common integration domains and will
build a compatible Action call for them. These have a lot of variation because Home Assistant actions
have a lot of variation! Generic Transports handling of these means you can create multi-channel
notifications without worrying too much about the variety of `data` mappings etc.

| Domain                        | Action Data                                                                                                                                                 | Target Data             |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------|
| notify ( `send_message` only) | `message` and `title` only                                                                                                                                  | `entity_id` map         |
| notify ( other actions )      | `message` and `title` plus all `data` elements                                                                                                              | big list of all targets |
| input_text                    | `value` with message                                                                                                                                        | `entity_id` map         |
| switch                        | Empty                                                                                                                                                       | `entity_id` map         |
| mqtt                          | All [permitted](https://www.home-assistant.io/integrations/mqtt/#action-mqttpublish) `data` elements. `payload` set to message value if not already defined | Empty                   |
| siren                         | All [permitted](https://www.home-assistant.io/integrations/siren/#action-sirenturn_on) `data` elements                                                      | `entity_id` map         |
| light                         | All [permitted](https://www.home-assistant.io/integrations/light/#action-lightturn_on) `data` elements                                                      | `entity_id` map         |
| rest_command | All of `data | Empty |
| script (`turn_on` and `turn_off` only) | `variables` contains a mapping of `message`,`title` plus any `variables` items in `data`. Other `data` elements added in their own right  | `entity_id` map |
| script (script name as action) | `message` and `title` plus all `data` elements | `entity_id` map |
| *default* |  `message` and `title` plus all `data` elements | big list of all targets |

### Input Text Integration

`input_text` can be used with ESP32, APIs and similar to pass text.

Configure a delivery:

```yaml
delivery:
  esp_screen:
    transport: generic
    action: input_text.set_value
    target: input_text.my_esp32
```

The `message` value on the notification will be passed as the `value` on the `data` section. See [Input Text Integration](https://www.home-assistant.io/integrations/input_text/) for more on that.

### Other Actions

The `data` supplied will be passed directly as the Action Data, message and title will be dropped as likely to be a problem for `switch`,`script` etc integrations.

If you have an action that is not supported, but it requires a similar Home Assistant Action call as one it does support, then the `handle_as_domain` option can be used.

```yaml
delivery:
  light_flasher:
  action: flashywashy.flash_me_now
  options:
    handle_as_domain: light
```

Alternatively, if the custom action call is failing because of `data` elements from the notification
it can't handle, you can control which keys are included, in this example, all keys that don't match the pattern will be dropped (test is made using Python's `re.fullmatch`):

```yaml
delivery:
  light_flasher:
  action: zigzag.zig
  options:
    data_keys_include_re:
      - enabled
      - value
      - zig.*
```

It also works the other way round, or indeed both together, with excluding, so all `data` keys
are passed, except selected ones

```yaml
delivery:
  light_flasher:
  action: zigzag.zig
  options:
    data_keys_exclude_re:
      - duration
      - volume
```


!!! tip
    If using Generic to trigger bells, sirens or other noises, consider the [Chime Transport Adaptor](chime.md), which makes that easier, especially if working with a mix of audio devices.
