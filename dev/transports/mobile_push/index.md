# Mobile Push Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/mobile_push/

| Transport ID  | Source                                                                                                                           | Requirements                                                                                              | Optional |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------- |
| `mobile_push` | [`mobile_push.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/mobile_push.py) | [Companion App Notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic) | -        |

## Discovery

**Default delivery.** If at least one Companion App device is registered (a `mobile_app` config entry exists) and no `mobile_push` delivery is configured, a `mobile_push` delivery is generated automatically and fires on every notification, with targets resolved per-recipient from the HA Companion App at delivery time.

Send a push message out, with option for camera integration, mobile actions, and translate general priority to Apple specific push priority.

Some functionality may also work with Android push, though has not been tested.

Although Supernotify will automatically set most useful mobile push options, its also possible to directly set them, as in this example:

```yaml
  - action: supernotify.notify
    data:
      message: Movement at garden gate
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

Info

This has not been tested with Android, although both Apple and Android devices share same common core mobile push notifications. Pull Requests for adding Android functionality are welcome.

## Video on Apple Devices

Apple's mobile apps, on iPhone, iPad and Mac, can't always show an `.mp4` video attached to a push, such as the clip the Frigate blueprint adds. Set the `apple_drop_mp4` option to leave `.mp4` video out of pushes to Apple devices, both the `video` URL and an `attachment` pointing at an `.mp4`. Images are kept, and Android devices still get the video.

```yaml
delivery:
  mobile_push:
    options:
      apple_drop_mp4: true
```

To switch it on for every mobile push delivery, turn on **Leave video out of Apple pushes** in **Settings** > **Devices & services** > **Supernotify** > **Configure** > **Delivery Control**.

## Notification Grouping

Set `mobile_push_group` in `extra_data:` to visually stack notifications together on the device (iOS thread-id / Android notification group):

```yaml
  - action: supernotify.notify
    data:
      message: Someone is at the front door
      extra_data:
        mobile_push_group: security
```

If left unset, a notification with `media.camera_entity_id` is grouped under that camera's entity id automatically; otherwise it's left ungrouped, so it appears on its own rather than being stacked with unrelated notifications. Critical-priority notifications are never grouped - iOS doesn't support it for them.

Note

Don't confuse this with [Action Groups](https://supernotify.rhizomatics.org.uk/latest/usage/mobile_actions/#action-groups) - `action_groups:` is Supernotify's own unrelated concept for reusable sets of actionable-notification buttons. The name clash is with the Companion App's own `group` attribute, not with Supernotify's action groups.

## Default Delivery

A default Delivery called `mobile_push` will be automatically generated for Mobile Push transport if no explicit ones created, since this is the new standard HomeAssistant notification provider. If you don't want to use it, then use configuration as below:

```yaml
transports:
  mobile_push:
    disabled: false
```

### Auto generating targets

By default, where no explicit target is given, mobile push will send to all known devices of all known recipients ( usually the list of [Person](https://www.home-assistant.io/integrations/person/) integration entries in Home Assistant, and mobile apps found in Home Assistant that have their `user_id` and Notify Entities available), and filter those recipients by occupancy status if wanted in the Delivery configuration.

Mobile Push can also do its own device discovery and ignore recipients. If you want to switch off that behaviour, and drive it only by the defined recipients, then switch on device discovery.

Configuration snippet

```yaml
transports:
  mobile_push:
    delivery_defaults:
      options:
        device_discovery: true
```

By default this will look for all `mobile_app` devices, and can be narrowed down by using the `device_model_select`,`device_manufacturer_select`, `device_area_select`, `device_label_select` and `device_os_select` patterns.

Configuration snippet

```yaml
transports:
  mobile_push:
    delivery_defaults:
      options:
        device_discovery: true
        device_label_select:
          include:
            - parents
          exclude:
            - kids
        device_manufacturer_select:
          exclude:
            - Apple
            - Amazon
        device_model_select: .*Pixel.*
        device_os_select:
          exclude:
            - MacOS
            - iOS
```

You can also use the device `select` options if not using auto-discovery - this will then limit that delivery to matching devices when they have been auto-discovered at start-up for all deliveries, or have been manually defined for recipients.

## References

### Home Assistant Core

- [Mobile App Integration](https://www.home-assistant.io/integrations/mobile_app/)
- [Companion App Notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic)
- [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20mobile_app%22%20state%3Aopen)
