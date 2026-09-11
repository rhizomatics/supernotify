---
tags:
  - transport
  - mqtt
---
# MQTT Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `mqtt` | :material-github:[`mqtt.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/mqtt.py) | :material-home-assistant: [Notify MQTT Integration](https://www.home-assistant.io/integrations/notify.mqtt/) | - |

## Discovery

**Delivery (explicit selection).** If the MQTT integration's config entry exists and no `mqtt`
delivery is defined, an `mqtt` delivery is generated automatically — but since a topic has no
automatic mapping to a recipient or entity, it only fires when selected explicitly (`data:
{data: {delivery: [mqtt]}}` or a scenario), not by default. MQTT devices that already expose
themselves as notify entities are covered automatically by the
[`notify_entity`](notify_entity.md) transport's own default delivery instead.

Whilst [MQTT Notify Entities](https://www.home-assistant.io/integrations/notify.mqtt/) can be used for many cases, and the Supernotify `generic` can be used to send a payload to `mqtt.publish`, the specific MQTT integration can be easier to use.

- Payloads can be defined in YAML rather than escaped JSON, and will be JSONified if needed on delivery
- The action doesn't need to be specified, and the config will validate that a `topic` has been provided.

## Example

```yaml title="Example Notification"
- action: supernotify.notify
  data:
    message: ""
    delivery:
        mqtt:
            data:
                topic: notify/queue/1
                payload:
                  warning:
                    duration: 30
                    mode: emergency
                    level: low
```

## Reference

### Home Assistant
- [MQTT Integration](https://www.home-assistant.io/integrations/mqtt/#action-mqttpublish)
    - [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20mqtt%22%20state%3Aopen)
