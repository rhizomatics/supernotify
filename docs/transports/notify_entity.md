---
tags:
  - transport
  - notify_entity
---
# Notify Entity Transport Adaptor

This transport uses the new style Home Assistant notify entities, so accepts only a `message`,
`title` and `target`, plus an optional `data` specific to some entity types.

Targets for Notify Entities can be broader than `entity_id`, and can also be a `device`, `label` or `area`, the latter also being an alternate way of calling multiple notify entities at once.

A default Delivery will be automatically generated for Notify Entity transport if no explicit ones
created, since this is the new standard HomeAssistant notification provider. If you don't want to use it, then
use configuration as below:

```yaml
transports:
  notify_entity:
    disabled: false
```
