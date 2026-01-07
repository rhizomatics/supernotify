---
tags:
  - mqtt
  - sms
  - zigbee2mqtt
title: General Tips for Notifications
---
# General Notification Tips

Hints and suggestions for configuring non-SuperNotify notification in HomeAssistant.

## Self-hosted SMS

If you have a Mikrotik 4G router for broadband or fallback, then you can probably
send SMS notifications through it, using *Mikrotik SMS* custom component.

Set it up by adding `https://github.com/jeyrb/hass_mikrotik_sms` as a custom repo in HACS.

## Configuring an MQTT Siren with Zigbee2MQTT

Home Assistant added MQTT Siren support in 2022, though as of writing its not
yet automatically provisioned by Zigbee2MQTT, and its fussy to set up.

Here is an example working config for a Heiman HS2WD-E plugin Zigbee siren


```yaml
   - unique_id: downstairs_east_wing_heiman
    name: "Scullery Siren"
    default_entity_id: siren.downstairs
    json_attributes_topic: "zigbee2mqtt/Downstairs Siren"
    command_topic: "zigbee2mqtt/Downstairs Siren/set"
    availability:
      - topic: "zigbee2mqtt/Downstairs Siren/availability"
        value_template: "{{ value_json.state }}"
        payload_available: online
        payload_not_available: offline
    command_template: >
      {% if duration is not defined %}
      {% set duration = 30 %}
      {% endif %}
      {"warning":
        {"duration": {{int(duration,30)}},
         "mode": "{{tone|default("emergency")}}",
         "strobe": true,
         "strobe_duty_cycle": 10,
         "strobe_level": "very_high"
         }}
    command_off_template: '{"warning": {"duration": 1, "mode": "stop"}}'
    icon: mdi:alarm-light
    qos: 0
    optimistic: false
    retain: true
    support_duration: true
    support_volume_set: false
    available_tones:
      - emergency
      - stop

```

### Other Ideas

See the `maximal.yaml` example configuration in the `examples` directory of this repo
for more ideas of how to use SuperNotify.
