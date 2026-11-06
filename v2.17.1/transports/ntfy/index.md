# ntfy Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/ntfy/

| Transport ID | Source                                                                                                             | Requirements                                                         | Optional |
| ------------ | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | -------- |
| `ntfy`       | [`ntfy.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/ntfy.py) | [ntfy Integration](https://www.home-assistant.io/integrations/ntfy/) | -        |

## Motivation

[ntfy](https://ntfy.sh) is a privacy-first, self-hostable push notification service, with an official Home Assistant integration since 2025.5. The integration creates a `notify` entity for each topic, and an `ntfy.publish` action with priority levels, action buttons, scheduled delivery, image attachments and message updates.

The ntfy transport adds:

- SuperNotify's 5 priority levels mapped to ntfy's 1–5
- Camera snapshots attached to the notification
- Action buttons checked before sending, so one bad button doesn't stop the message
- The tap-through URL defaulting to a [notification level action](https://supernotify.rhizomatics.org.uk/latest/usage/mobile_actions/#notification-level-actions)

## Targets

Target the `notify` entity of an ntfy topic, for example `notify.ntfy_alerts`, directly or through a recipient. The `ntfy` delivery is selected for these entities ahead of the generic [Notify Entity](https://supernotify.rhizomatics.org.uk/latest/transports/notify_entity/index.md) one, without needing to be named.

Alternatively, fix the topic on a delivery with `ntfy_device_id`, the topic's device id, used when no ntfy entity is targeted. Find it in *Settings → Devices & services → ntfy*, or with the template `{{ device_id('notify.ntfy_alerts') }}`.

A delivery with neither is skipped.

## Data keys

All are optional, and only the fields `ntfy.publish` accepts are passed on: its schema rejects anything else, so `data` meant for other deliveries, like Mobile Push's `clickAction`, is dropped.

| Key                 | Type         | Default                   | Description                                                                                                          |
| ------------------- | ------------ | ------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `ntfy_device_id`    | `str`        | —                         | Device id of an ntfy topic, used when no ntfy `notify` entity is targeted                                            |
| `ntfy_priority`     | `int` 1–5    | from priority             | Override the priority (5=urgent, 1=min); anything else is ignored                                                    |
| `ntfy_tags`         | `list[str]`  | —                         | Tags, shown as emoji where they match an [ntfy shortcode](https://docs.ntfy.sh/emojis/), e.g. `["warning", "house"]` |
| `ntfy_click`        | `str` (URL)  | notification action `uri` | URL opened when the notification is tapped                                                                           |
| `ntfy_attach_image` | `bool`       | `false`                   | Attach the camera snapshot, from `media.camera_entity_id`                                                            |
| `ntfy_filename`     | `str`        | `snapshot.jpg`            | Filename for the attachment                                                                                          |
| `ntfy_icon`         | `str` (URL)  | —                         | JPEG or PNG icon URL                                                                                                 |
| `ntfy_markdown`     | `bool`       | `false`                   | Render the message as Markdown                                                                                       |
| `ntfy_delay`        | `str`        | —                         | Delay delivery: `"10m"`, `"1h30m"`, `"45s"` or `"HH:MM"`, between 10 seconds and 3 days                              |
| `ntfy_sequence_id`  | `str`        | —                         | Id that a later notification with the same id updates                                                                |
| `ntfy_email`        | `str`        | —                         | Also forward to this e-mail address                                                                                  |
| `ntfy_actions`      | `list[dict]` | —                         | Up to 3 action buttons, see below                                                                                    |

A `snapshot_url` in `media` is attached whether or not `ntfy_attach_image` is set. Either way, the image is sent as a URL, so ntfy must be able to reach Home Assistant's media folder.

### Action buttons

```yaml
ntfy_actions:
  - action: view
    label: Open dashboard
    url: https://ha.example.com/lovelace/security
    clear: true
  - action: http
    label: Acknowledge
    url: https://ha.example.com/api/webhook/ack_alarm
    method: POST
  - action: broadcast
    label: Intent
    intent: io.heckel.ntfy.USER_ACTION
  - action: copy
    label: Copy code
    value: "1234"
```

A button without an `action` or `label` is dropped with a warning, and only the first 3 are sent.

## Example

Supernotify Configuration

```yaml
delivery:
  ntfy_security:
    transport: ntfy
    inclusion: default
    data:
      ntfy_device_id: "abc123def456"
      ntfy_attach_image: true
      ntfy_tags: [house, rotating_light]
```

Notification

```yaml
action: supernotify.notify
data:
  message: "Motion detected at entrance"
  title: "Front Camera"
  media:
    camera_entity_id: camera.front_door
```

Or, with no delivery configured, send to the topic's entity:

```yaml
action: supernotify.notify
data:
  message: "Washing done"
  target: notify.ntfy_alerts
  extra_data:
    ntfy_tags: [tshirt]
```

## Discovery

**Delivery (default selection).** If the `ntfy` integration is configured and no `ntfy` delivery is defined, an `ntfy` delivery is generated automatically. It's used when a target is one of the integration's `notify` entities, and otherwise not, since it has no topic to send to.
