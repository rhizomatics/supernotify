# Recipe - MQTT

## Purpose

Notify by publishing to an MQTT topic, for example a siren that doesn't support the *Siren* integration.

## Implementation

Uses the **Generic** method.

## Example Configuration

```yaml
delivery:
  downstairs_siren:
      method: generic
      action: mqtt.publish
      selection: scenario
      priority:
        - critical
      data:
        topic: zigbee2mqtt/Downstairs Siren/set
        payload: '{"warning": {"duration": 30,
                  "mode": "emergency",
                  "level": "low",
                  "strobe": true,
                  "strobe_duty_cycle": 10,
                  "strobe_level": "very_high" }}'
```
