---
tags:
  - transport
  - generic
---
# Generic Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `generic` | :material-github:[`generic.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/generic.py) | - | *Any Home Assistant action from core or custom integration* |

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
it can't handle, you can control which keys are included, in this example, all keys that don't match the pattern will be dropped:

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
