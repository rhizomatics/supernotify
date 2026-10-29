# Mobile Push Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/mobile_push/

| Transport ID  | Source                                                                                                                           | Requirements                                                                                              | Optional |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------- |
| `mobile_push` | [`mobile_push.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/mobile_push.py) | [Companion App Notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic) | -        |

Send a push message to the Companion App on iPhone, iPad, Mac and Android, with camera images, mobile actions, and Supernotify's priority translated into what each platform uses for it.

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

The `push` block is for Apple devices only, and Supernotify adds to it rather than replacing it - the `sound` above is kept, alongside the `interruption-level` that Supernotify sets from the priority.

Each phone gets only its own platform's data: `push`, `subtitle` and `url` go to Apple devices, and `ttl`, `priority`, `channel` and `clickAction` go to Android. The platform comes from the `os_name` the Companion App registers, or from the manufacturer if no `os_name` is registered. A device Home Assistant doesn't know gets both.

## Data Keys

Set these in `extra_data:`, or in a delivery's `data:`. Supernotify removes them and turns them into what the Companion App expects.

| Key                               | Platform | Usage                                                                                                                                                  |
| --------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `mobile_push_critical_level`      | Apple    | `interruption-level` to use instead of the one from the priority: `passive`, `active`, `time-sensitive` or `critical`                                  |
| `mobile_push_subtitle`            | Apple    | Line shown between the title and the message                                                                                                           |
| `mobile_push_critical_ttl`        | Android  | FCM `ttl`, how long it may wait to be delivered. `0` for a `critical` notification if not set                                                          |
| `mobile_push_critical_priority`   | Android  | FCM `priority`, `high` or `normal`. `high` for a `critical` notification if not set                                                                    |
| `mobile_push_channel_override`    | Android  | Notification `channel`, which sets its sound and vibration                                                                                             |
| `mobile_push_alarm_stream`        | Android  | Use the `alarm_stream` channel, which sounds through Do Not Disturb and silent mode                                                                    |
| `mobile_push_alarm_stream_max`    | Android  | As `mobile_push_alarm_stream`, and TTS at full alarm volume                                                                                            |
| `mobile_push_tts_text`            | Android  | Text the phone speaks, see [below](#android-commands-and-spoken-text)                                                                                  |
| `mobile_push_tts_delay`           | Android  | Seconds to wait after the notification before speaking, default `5`                                                                                    |
| `mobile_push_tts_locale`          | Android  | Language for the spoken text, for example `en-GB`                                                                                                      |
| `mobile_push_tts_engine`          | Android  | TTS engine package, for example `com.google.android.tts`                                                                                               |
| `mobile_push_command_dnd`         | Android  | Change Do Not Disturb before the notification                                                                                                          |
| `mobile_push_command_ringer_mode` | Android  | Change the ringer mode before the notification                                                                                                         |
| `mobile_push_command_screen_on`   | Android  | Turn the screen on before the notification                                                                                                             |
| `mobile_push_group`               | Both     | Stack notifications together, see [Notification Grouping](#notification-grouping)                                                                      |
| `mobile_push_notification_tag`    | Both     | `tag`, so a later notification with the same tag replaces this one                                                                                     |
| `mobile_push_clear_notification`  | Both     | Clear the notification with this `mobile_push_notification_tag` from the phone. This is sent *instead of* the notification, so its message isn't shown |

Any other key in `data` is passed to the Companion App as it is.

## Critical on Android

A `critical` notification goes to Android phones the way the [companion app documents critical notifications](https://companion.home-assistant.io/docs/notifications/critical-notifications): `ttl: 0` and `priority: high`, so a phone saving battery gets it straight away, and the `alarm_stream` channel, so it sounds even with Do Not Disturb on or the phone on silent - the Android counterpart of iOS's `interruption-level: critical`.

The companion app's own `channel` and `ttl`, when set in the data, are kept as they are, so a critical notification can still use a channel of its own (`mobile_push_critical_priority: normal` changes the `high` priority):

```yaml
  - action: supernotify.notify
    data:
      message: Smoke in the kitchen
      priority: critical
      delivery:
        mobile_push:
          data:
            channel: smoke_alarm
```

Tip

Some phones (Samsung One UI for one) also need the Home Assistant app allowed as an exception to Do Not Disturb, in the phone's own settings.

## Android Commands and Spoken Text

The companion app takes [notification commands](https://companion.home-assistant.io/docs/notifications/notification-commands) and TTS as the `message` of a call of their own, so Supernotify sends them that way, to Android phones only: `mobile_push_command_dnd` (`alarms_only`, `priority_only`, `total_silence`, `off`), `mobile_push_command_ringer_mode` (`normal`, `silent`, `vibrate`) and `mobile_push_command_screen_on` each go just before the notification, and `mobile_push_tts_text` 5 seconds after it, so the notification's own sound isn't cut off (`mobile_push_tts_delay` changes that, `0` for straight away) - for a `critical` notification on the alarm stream at full volume (`alarm_stream_max`, the app puts the volume back afterwards), since a watch's alarm volume can be too low to hear:

```yaml
  - action: supernotify.notify
    data:
      message: Water leak under the sink
      priority: critical
      extra_data:
        mobile_push_command_screen_on: true
        mobile_push_tts_text: Water leak under the sink
```

Note

`command_dnd` needs a permission the companion app asks for the first time it's used.

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

## Tap URL and Live View

A [notification level action](https://supernotify.rhizomatics.org.uk/latest/usage/mobile_actions/#notification-level-actions) sets what opens when the notification is tapped, for both platforms - it becomes `url` on iOS and `clickAction` on Android. A path such as `/lovelace/cameras` opens in the Companion App, a full URL in the browser.

With a `camera_entity_id`, Supernotify gets the image itself - from the `snapshot_url` if there is one, otherwise from the camera - and attaches it, so the phone doesn't need to reach the camera. Only when no image can be got is the phone given the camera's `entity_id` to fetch from instead (or an [alternative camera](https://supernotify.rhizomatics.org.uk/latest/configuration/multimedia/#cameras) that's available), which an iPhone shows as the live stream when the notification is expanded. A notification with only a `snapshot_url` passes that URL to the phone as its image.

```yaml
  - action: supernotify.notify
    data:
      message: Car on the driveway
      media:
        snapshot_url: https://frigate.local/api/events/1696512345.123-abc/snapshot.jpg
        camera_entity_id: camera.driveway
      actions:
        - level: notification
          uri: /lovelace/cameras
```

## Default Delivery

To stop the default delivery described [above](#discovery) being generated, switch the transport off:

```yaml
transports:
  mobile_push:
    enabled: false
```

### Auto generating targets

By default, where no explicit target is given, mobile push will send to all known devices of all known recipients ( usually the list of [Person](https://www.home-assistant.io/integrations/person/) integration entries in Home Assistant, and mobile apps found in Home Assistant that have their `user_id` and a notify action available), and filter those recipients by occupancy status if wanted in the Delivery configuration.

Mobile Push can also find devices itself, whoever they belong to. With device discovery switched on, the `mobile_app` devices found at start-up become the delivery's own target. How that combines with the recipients' devices follows the delivery's [`target_usage`](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/#controlling-targets) - `fixed` sends only to the discovered devices.

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

### Explicit Targets

To pin a delivery to one specific device, give its `mobile_app_id` as a bare value - the same form used for a device under `recipients` (see [People](https://supernotify.rhizomatics.org.uk/latest/configuration/people/index.md)) - not the dotted `notify.mobile_app_<device>` service-call form:

Fixed target on a delivery

```yaml
delivery:
  alert_phone:
    transport: mobile_push
    target_usage: fixed
    target:
      - mobile_app_my_phone
```

`notify.mobile_app_my_phone` is the name of the Companion App's notify action, not a `mobile_app_id` - as a target it's taken as an `entity_id` - mobile_push doesn't consume `entity_id` targets at all, so a dotted target here resolves to nothing, and the delivery silently falls back to its normal recipient-based target instead of the one device you named. `target_usage: fixed` is also needed if you don't want that recipient-based fallback - without it, the configured `target:` is *added to* the recipient-resolved targets rather than replacing them (see [Controlling Targets](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/#controlling-targets) and [Targets](https://supernotify.rhizomatics.org.uk/latest/usage/targets/#target-categories)).

## Discovery

**Default delivery.** If at least one Companion App device is registered (a `mobile_app` config entry exists) and no `mobile_push` delivery is configured, a `mobile_push` delivery is generated automatically and fires on every notification, with targets resolved per-recipient from the HA Companion App at delivery time.

## References

### Home Assistant Core

- [Mobile App Integration](https://www.home-assistant.io/integrations/mobile_app/)
- [Companion App Notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic)
- [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20mobile_app%22%20state%3Aopen)
