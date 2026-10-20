# Notify Entity Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/notify_entity/

| Transport ID    | Source                                                                                                                               | Requirements                                                                    | Optional |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------- | -------- |
| `notify_entity` | [`notify_entity.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/notify_entity.py) | [Notify Entity Integration](https://www.home-assistant.io/integrations/notify/) | -        |

This transport uses the new style Home Assistant notify entities, through the `notify.send_message` action, which accepts only a `message` and `title`. Whether the title is shown is up to each entity.

## Targets

Any `notify.*` entity can be a target. An `area_id`, `floor_id` or `label_id` can also be used, and is turned into the notify entities in it before delivery, as is a `group` into its members. This is an easy way of calling several notify entities at once. Devices can't be used as targets for this transport.

This is the catch-all for notify entities. Ones that belong to an integration with its own transport, such as [HTML5](https://supernotify.rhizomatics.org.uk/latest/transports/html5/index.md) or [Alexa Devices](https://supernotify.rhizomatics.org.uk/latest/transports/alexa_devices/index.md), are left to that transport.

Supernotify's own notify entities - for a recipient, or for a scenario or delivery with a `notify_entity` - are not called when given as a target in a notification action. The recipient is targeted, or the scenario applied or delivery selected, directly instead.

This transport never sends to Supernotify's own notify entities. In the `target` of a delivery, scenario or recipient, a recipient's entity is replaced by the recipient, and a scenario's or delivery's is dropped with a warning. See [Scenario Notify Entity](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/#notify-entity) for the current limitations.

## Discovery

**Default delivery.** If at least one `notify.*` entity exists in the house and no `notify_entity` delivery is configured, a `notify_entity` delivery is generated automatically. It is used whenever a notification targets a notify entity that no more specific transport has taken.

## Default Delivery

If you don't want to use the automatically generated default delivery, then use configuration as below, or configure your own delivery for the transport.

```yaml
transports:
  notify_entity:
    enabled: false
```

## Example

Example Notification

```yaml
- action: supernotify.notify
  data:
    message: "Motion detected at the front door"
    target:
        - notify.mobile_app_pixel
```

Example Notification to every notify entity in the kitchen, and those labelled display

```yaml
- action: supernotify.notify
  data:
    message: "Dinner is ready"
    target:
        area_id: kitchen
        label_id: display
```
