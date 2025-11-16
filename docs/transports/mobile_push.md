# Mobile Push Transport

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
