---
tags:
  - transport
  - notify_entity
---
# Notify Entity Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `notify_entity` | :material-github:[`notify_entity.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/notify_entity.py) | :material-home-assistant: [Notify Entity Integration](https://www.home-assistant.io/integrations/notify/) | - |


This transport uses the new style Home Assistant notify entities, so accepts only a `message`,
`title` and `target`, plus an optional `data` specific to some entity types.

Targets for Notify Entities can be broader than `entity_id`, and can also be a `device`, `label` or `area`, the latter also being an alternate way of calling multiple notify entities at once.

## Discovery

**Default delivery.** If at least one `notify.*` entity exists in the house and no
`notify_entity` delivery is configured, a `DEFAULT_notify_entity` delivery is generated
automatically and fires on every notification, since this is the standard Home Assistant
notification provider.

## Default Delivery

If you don't want to use the automatically generated default delivery, then
use configuration as below, or configure your own delivery for the transport.

```yaml
transports:
  notify_entity:
    disabled: false
```

## Example

```yaml title="Example Notification"
- action: supernotify.notify
  data:
    message: "Motion detected at the front door"
    target:
        - notify.mobile_app_pixel
```
