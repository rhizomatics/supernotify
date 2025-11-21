---
tags:
  - transport
  - mqtt
---
# MQTT Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `mqtt` | :material-github:[`mqtt.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/mqtt.py) | :material-home-assistant: [Notify MQTT Integration](https://www.home-assistant.io/integrations/notify.mqtt/) | - |


Whilst [MQTT Notify Entities](https://www.home-assistant.io/integrations/notify.mqtt/) can be used for many cases, and the Supernotify `generic` can be used to send a payload to `mqtt.publish`, the specific MQTT integration can be easier to use.

- Payloads can be defined in YAML rather than escaped JSON, and will be JSONified if needed on delivery
- The action doesn't need to be specified, and the config will validate that a `topic` has been provided.
