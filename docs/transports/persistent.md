---
tags:
  - transport
  - persistent
---
# Persistent Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `persistent` | :material-github:[`persistent.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/persistent.py) | :material-home-assistant: [Persistent Notification Integration](https://www.home-assistant.io/integrations/persistent_notification/) | - |


Place a notification on Home Assistant application screen.

The `title` and `message` are shown as they are, with no other `data`, and no target.

Pass a `notification_id` in the action's `extra_data`, or fixed in the delivery's `data`. A later notification with
the same ID replaces the earlier one, rather than adding another, and without an ID a new
notification is always added.

Unlike other discovered transports, the `persistent` delivery isn't selected by default, since a popup for
every notification would be intrusive. Name it in `delivery`, or set `inclusion` to include it.

## Example

A `persistent` delivery is created automatically, so send like:

```yaml
- action: supernotify.notify
  data:
    message: Testing an e-mail that also shows as persistent notification
    target:
      - homeowner@24acaciaavenue.com
    delivery:
      - email
      - persistent
    extra_data:
      notification_id: front_door
```


## References

### Home Assistant
- [Persistent Notification Integration](https://www.home-assistant.io/integrations/persistent_notification/)
    - [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20persistent_notification%22%20state%3Aopen)
