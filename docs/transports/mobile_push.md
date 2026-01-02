---
tags:
  - transport
  - mobile_push
  - iOS
  - actionable_notifications
---
# Mobile Push Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `mobile_push` | :material-github:[`mobile_push.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/mobile_push.py) | :material-home-assistant: [Companion App Notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic) | - |


Send a push message out, with option for camera integration, mobile actions, and
translate general priority to Apple specific push priority.

Some functionality may also work with Android push, though has not been tested.

Although Supernotify will automatically set most useful mobile push options,
its also possible to directly set them, as in this example:

```yaml
  - action: notify.supernotify
    data:
      message: Movement at garden gate
      data:
        priority: high
        media:
          camera_entity_id: camera.porch
          camera_ptz_preset: garden_gate
        action_groups:
          - security_actions
        delivery:
          mobile_push:
            data:
              tag: "backyard-motion-detected"
              presentation_options:
                - alert
                - badge
              push:
                sound:
                  name: "US-EN-Alexa-Motion-Detected-Generic.wav"
                  volume: 1.0
```

!!! info
    This has not been tested with Android, although both Apple and Android devices share same
    common core mobile push notifications. Pull Requests for adding Android functionality are welcome.

## Default Delivery

A default Delivery called `DEFAULT_mobile_push` will be automatically generated for Mobile Push transport if no explicit ones
created, since this is the new standard HomeAssistant notification provider. If you don't want to use it, then
use configuration as below:

```yaml
transports:
  mobile_push:
    disabled: false
```

### Auto generating targets

By default, mobile push will send to all the recipients defined, which is usually the list of [Person](https://www.home-assistant.io/integrations/person/) integration entries in Home Assistant.

To send out to all mobile apps, regardless of `recipient` or `Person` configuration, configure device discovery
at the transport level.

```yaml title="Configuration snippet"
transports:
  mobile_push:
    device_discovery: true
```

By default this will look for all `mobile_app` devices, and can be narrowed down by using the `device_model_include`,`device_model_exclude`,`device_manufacturer_include` and `device_manufacturer_exclude` patterns.

```yaml title="Configuration snippet"
transports:
  mobile_push:
    device_discovery: true
    device_manufacturer_exclude:
      - Apple
    device_model_exclude:
      - .*TV
```


## References

### Home Assistant Core
- [Mobile App Integration](https://www.home-assistant.io/integrations/mobile_app/)
  - [Notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic)
  - [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20mobile_app%22%20state%3Aopen)
