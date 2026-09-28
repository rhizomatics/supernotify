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

**Delivery (default selection).** If the MQTT integration's config entry exists and no `mqtt`
delivery is defined, an `mqtt` delivery is generated automatically, and reaches it automatically
too - no need to name `mqtt` in `delivery:` or a scenario - whenever the notification's target
includes a value qualified with the dedicated `topic` category (`target: {topic: "..."}`), the
same way an email address reaches the `email` delivery. Without a `topic:` target and without
being named explicitly, the delivery is simply skipped, not attempted - it doesn't spam a "No
topic for publication" warning on every unrelated notification.

A topic can also still be given as a `data:` keyword instead of a target, for backward
compatibility, but only when the call actually asks for `mqtt` by name - naming it explicitly
(`delivery: {mqtt: {data: {topic: "..."}}}}`) is what makes a `data:`-only topic count as
something genuinely being asked for, rather than the auto-generated delivery blindly attempting
every notification regardless of relevance. MQTT devices that already expose themselves as
notify entities are covered automatically by the [`notify_entity`](notify_entity.md) transport's
own default delivery instead.

Whilst [MQTT Notify Entities](https://www.home-assistant.io/integrations/notify.mqtt/) can be used for many cases, and the Supernotify `generic` can be used to send a payload to `mqtt.publish`, the specific MQTT integration can be easier to use.

- Payloads can be defined in YAML rather than escaped JSON, and will be JSONified if needed on delivery
- The action doesn't need to be specified, and the config will validate that a `topic` has been provided.

## Example

The topic should be supplied as a `target`, not `data.topic`, which is only supported for
backward compatibility - see below. If both are given, `target` takes precedence. Multiple
targets publish the same payload to each topic in turn.

Giving a `topic:`-qualified target is enough on its own - the `mqtt` delivery doesn't need to be
named:

```yaml title="Example Notification with topic as target"
- action: supernotify.notify
  data:
    message: "this will be the MQTT payload"
    target: topic:notify/queue/1
```

Naming `mqtt` explicitly still works the same way, and is needed to attach delivery-specific
`data:` like a structured payload:

```yaml title="Example Notification"
- action: supernotify.notify
  data:
    message: ""
    delivery:
        mqtt:
            target: topic:notify/queue/1
            data:
                payload:
                  warning:
                    duration: 30
                    mode: emergency
                    level: low
```

A topic given as `data.topic` instead of a target only takes effect when `mqtt` is named
explicitly like this - it's how a fixed-topic MQTT delivery configured directly in YAML
(`delivery: {mqtt: {data: {topic: ...}}}}`) still works, predating the `target:` form:

```yaml title="Example Notification with legacy data.topic"
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
