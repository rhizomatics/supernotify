# MQTT Transport Adaptor

| Transport ID | Source                                                                                                             | Requirements                                                                       | Optional |
| ------------ | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- | -------- |
| `mqtt`       | [`mqtt.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/mqtt.py) | [Notify MQTT Integration](https://www.home-assistant.io/integrations/notify.mqtt/) | -        |

## Discovery

**Delivery (explicit selection).** If the MQTT integration's config entry exists and no `mqtt` delivery is defined, an `mqtt` delivery is generated automatically — but since a topic has no automatic mapping to a recipient or entity, it only fires when selected explicitly (`data: {data: {delivery: [mqtt]}}` or a scenario), not by default. MQTT devices that already expose themselves as notify entities are covered automatically by the [`notify_entity`](https://supernotify.rhizomatics.org.uk/transports/notify_entity/index.md) transport's own default delivery instead.

Whilst [MQTT Notify Entities](https://www.home-assistant.io/integrations/notify.mqtt/) can be used for many cases, and the Supernotify `generic` can be used to send a payload to `mqtt.publish`, the specific MQTT integration can be easier to use.

- Payloads can be defined in YAML rather than escaped JSON, and will be JSONified if needed on delivery
- The action doesn't need to be specified, and the config will validate that a `topic` has been provided.

## Example

Example Notification

```yaml
- action: supernotify.notify
  data:
    message: ""
    delivery:
        mqtt:
            target: notify/queue/1
            data:
                payload:
                  warning:
                    duration: 30
                    mode: emergency
                    level: low
```

The topic can also be supplied as a `target` instead of `data.topic` - useful for selecting the topic per scenario or recipient rather than hard-coding it into the delivery. If both are given, `target` takes precedence. Multiple targets publish the same payload to each topic in turn.

Example Notification with topic as target

```yaml
- action: supernotify.notify
  data:
    message: "this will be the MQTT payload"
    target: topic:notify/queue/1
```

## Reference

### Home Assistant

- [MQTT Integration](https://www.home-assistant.io/integrations/mqtt/#action-mqttpublish)
  - [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20mqtt%22%20state%3Aopen)
