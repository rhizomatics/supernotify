---
tags:
  - transport
  - generic
---
# Generic Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `generic` | :material-github:[`generic.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/generic.py) | - | *Any Home Assistant action from core or custom integration* |


Use to call any actiom, including 'legacy' Notification action (previously known in Home Assistant as 'service' ), that is one not using the newer `NotifyEntity` model.

If action is in `notify` domain, then `message`,`title`,`target` and `data` will be
passed in the Action (Service) Data, otherwise the `data` supplied will be passed directly
as the Action Data.

```yaml
    - action: notify.supernotify
      data:
        title: "My Home Notification"
        message: "Notify via custom chat"
        delivery:
            chat_notify:
                data:
                    channel: 3456
    - action: notify.supernotify
      data:
        delivery:
            mqtt_notify:
                data:
                  topic: alert/family_all
                  payload: something happened
```
