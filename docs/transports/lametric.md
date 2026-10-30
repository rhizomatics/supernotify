---
tags:
  - transport
  - lametric
  - IoT
---
# LaMetric TIME Transport Adaptor

| Transport ID | Source      | Requirements | Optional |
| ------------ | ----------- | ------------ | -------- |
| `lametric` | :material-github:[`lametric.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/lametric.py) | :material-home-assistant: [LaMetric Integration](https://www.home-assistant.io/integrations/lametric/) | - |

## Motivation

LaMetric TIME is a smart display with a [Home Assistant integration](https://www.home-assistant.io/integrations/lametric/),
discovered automatically on the network, which provides `lametric.message` for text and `lametric.chart` for bar charts.

The LaMetric transport adds:

* SuperNotify's priority mapped to LaMetric's display settings - cycles, sound, icon and icon type
* Bar charts from `lametric_chart_data`, for example the last few sensor readings
* Optionally, message text shortened for the small display, with URLs removed

The display has no room for a title, so only the message is shown.

## Targets

Target the `notify` entity the LaMetric integration creates for each display, for example `notify.lametric_kitchen`,
directly or through a recipient. The `lametric` delivery is selected for these entities ahead of the generic
[Notify Entity](notify_entity.md) one, without needing to be named, and each display targeted is sent the notification.

Alternatively, fix the display on a delivery with `device_id` in its `data`, used when no LaMetric entity is targeted.
Find it in *Settings → Devices & services → LaMetric*, or with the template `{{ device_id('notify.lametric_kitchen') }}`.

A delivery with neither is skipped.

## Priority Mapping

Each of these can be overridden with the data keys below.

| SuperNotify | LaMetric priority | cycles | icon_type | sound  | icon  |
| --          | --                | --     | --        | --     | --    |
| critical    | critical          | 0 (until dismissed) | alert | alarm1 | a1784 |
| high        | warning           | 2      | alert     | knock-knock | i140 |
| medium      | info              | 1      | info      | notification | i2867 |
| low         | info              | 1      | none      | (silent) | i2867 |
| minimum     | info              | 1      | none      | (silent) | (none) |

## Data Keys

* `device_id` — the LaMetric device id, used when no LaMetric `notify` entity is targeted
* `lametric_sound` — a built-in sound, such as `alarm1`…`alarm13`, `bicycle`, `cash`, `dog`, `knock-knock`,
  `letter_email`, `notification`, `positive1`, `win`, `wind`
* `lametric_icon` — an icon id from the [LaMetric icon gallery](https://developer.lametric.com/icons), such as `i2867`
* `lametric_cycles` — times the notification is shown, `0` to stay until dismissed
* `lametric_icon_type` — `none`, `info` or `alert`
* `lametric_chart_data` — a list of numbers, sent as a bar chart with `lametric.chart` instead of the message
* `lametric_simplify` — shorten the message and remove URLs (default `false`)

Other `data` isn't passed on, since the LaMetric actions reject what they don't know.

## Example Configuration

```yaml title="Supernotify Configuration"
delivery:
  lametric:
    transport: lametric
    data:
      device_id: "49b6e2186ef37e164818aacb9cea1f53"

  lametric_doorbell:
    transport: lametric
    data:
      device_id: "49b6e2186ef37e164818aacb9cea1f53"
      lametric_sound: "knock-knock"
      lametric_icon: "i140"
      lametric_icon_type: "alert"
      lametric_cycles: 2
```

## Example Call

```yaml
action: supernotify.notify
data:
  message: "Temperature trend"
  delivery:
    lametric:
      data:
        lametric_chart_data: [18, 20, 22, 21, 23, 24]
        lametric_cycles: 3
```

And a message to a display's entity, with no delivery configured:

```yaml
action: supernotify.notify
data:
  message: "Washing done"
  target: notify.lametric_kitchen
```

Or to the configured delivery, with the archived result:

```yaml
action: supernotify.notify
data:
  message: "LaMetric smoke test - if you see this on the display, it works!"
  delivery: lametric
```

```json
{
  "deliveries": {
    "lametric": {
      "delivered": [{
        "calls": [{
          "domain": "lametric", "action": "message",
          "action_data": {
            "device_id": "49b6e2186ef37e164818aacb9cea1f53",
            "message": "LaMetric smoke test - if you see this on the display, it works!",
            "cycles": 1,
            "priority": "info",
            "icon_type": "info",
            "icon": "i2867",
            "sound": "notification"
          }
        }]
      }]
    }
  }
}
```

## Discovery

**Delivery (default selection).** If the `lametric` integration is configured and no `lametric` delivery is
defined, a `lametric` delivery is generated automatically. It's used when a target is one of the integration's
`notify` entities, and otherwise not, since it has no display to send to.
