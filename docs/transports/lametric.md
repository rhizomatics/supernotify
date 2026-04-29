---
tags:
  - transport
  - lametric
  - IoT
---
# LaMetric TIME Transport Adaptor

## Motivation


LaMetric TIME is a popular IoT display device with [native Home Assistant integration](https://www.home-assistant.io/integrations/lametric/) (auto-discovered via mDNS/SSDP). The HA lametric integration exposes two services: lametric.message (text notifications) and lametric.chart (bar chart data).

While LaMetric can be used with the [Generic Transport](generic.md) for basic text, this integration adds:

* Map SuperNotify's 5-level priority to LaMetric's display parameters (cycles, sound, icon, icon_type) automatically
* Send bar chart data (lametric.chart) for sensor visualization (temperature, CPU, battery)
* Apply icon type selection (alert = red flashing, info = blue, none) per priority
* Provide per-priority defaults for sound effects (alarm1, knock-knock, notification)

## Requirements

* Home Assistant LaMetric integration installed and configured (auto-discovery)
* `device_id` available in HA device registry (Settings → Devices → LaMetric → Device ID)
* No additional Python packages required

## Priority Mapping

Priority Mapping

SuperNotify priority → LaMetric display parameters (all auto-applied, all overridable):

| SuperNotify | LaMetric priority | cycles | icon_type | sound  | icon  |
| --          | --                | --     | --        | --     | --    |
| critical.   | critical          | 0 (∞)  | alert.    | alarm1 | a1784 |
| high        | warning           | 2      | alert     | knock-knock | i140 |
| medium | info | 1 | info | notification | i2867 |
| low | info | 1 | none | (silent) | i2867 |
| minimum | info | 1 | none | (silent) | —

All lametric_* keys are removed from ``data` before calling the underlying LaMetric Home Assistant action.

## Example Configuration

```yaml title="Supernotify configuration snippet"
# Minimal — device_id required, all other params auto from priority
deliveries:
  - name: lametric
    transport: lametric
    data:
      device_id: "49b6e2186ef37e164818aacb9cea1f53"

# Doorbell — explicit overrides
  - name: lametric_campanello
    transport: lametric
    data:
      device_id: "49b6e2186ef37e164818aacb9cea1f53"
      lametric_sound: "knock-knock"
      lametric_icon: "i140"
      lametric_icon_type: "alert"
      lametric_cycles: 2

# Bar chart — temperature sensor (last 6 readings)
  - name: lametric_temperatura
    transport: lametric
    data:
      device_id: "49b6e2186ef37e164818aacb9cea1f53"
      lametric_chart_data: [18, 20, 22, 21, 23, 24]
      lametric_cycles: 3
```

## Example Call

This example presumes Supernotify configured with this delivery.

```yaml title="Supernotify configuration snippet"
lametric_test:
  transport: lametric
  selection: explicit
  data:
    device_id: "<lametric-device-uuid>"
    lametric_icon: "i2867"
    lametric_sound: "notification"
```

Then call this action ...

```yaml
action: notify.supernotify
data:
  message: "Test transport nativo LaMetric - Se vedi questo sul display LaMetric, funziona!"
  data:
    delivery_selection: fixed
    delivery:
      lametric_test:
        enabled: true
```

And the resulting archived notification looks like:

```json
{
  "delivered": 1, "failed": 0, "error_count": 0,
  "stats": { "total_duration_ms": 8.5, "delivery_success_rate": 1.0 },
  "deliveries": {
    "lametric_test": {
      "delivered": [{
        "calls": [{
          "domain": "lametric", "action": "message",
          "action_data": {
            "device_id": "<uuid>",
            "message": "Test transport nativo LaMetric - ...",
            "cycles": 1,
            "priority": "info",
            "icon_type": "info",
            "icon": "i2867",
            "sound": "notification"
          },
          "elapsed": 0.0085,
          "failed_calls": []
        }]
      }]
    }
  }
}
```
