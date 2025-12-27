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

## Default Delivery

A default Delivery called `DEFAULT_notify_entity` will be automatically generated for Notify Entity transport if no explicit ones
created, since this is the new standard HomeAssistant notification provider. If you don't want to use it, then
use configuration as below, or configure your own delivery for the transport.

```yaml
transports:
  notify_entity:
    disabled: false
```
