---
tags:
  - transport
  - mobile_push
  - iOS
---
# Mobile Push Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `mobile_push` | :material-github:[`mobile_push.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/mobile_push.py) | :material-home-assistant: [iOS Companion App Integration](https://www.home-assistant.io/integrations/ios/) | - |


Send a push message out, with option for camera integration, mobile actions, and
translate general priority to Apple specific push priority.

Some functionality may also work with Android push, though has not been tested.

Although Supernotify will automatically set most useful mobile push options,
its also possible to directly set them, as in this example:

```yaml
  - action: notify.supernotifier
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
