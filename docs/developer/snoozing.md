---
tags:
  - actionable_notifications
  - snoozing
---
# Snoozing

Snoozing can be selected from a mobile action, and made for a set time, or notifications can be silenced until further notice ( or currently until reboot, there is no persistence yet ).

Two HomeAssistant actions ( previously known as "services") are available to manage snoozes:

- `supernotify.clear_snoozes`
- `supernotify.enquire_snoozes`

Snooze context is also logged in the debug trace, which can be archived to the file system or MQTT topic.

### Mobile Actions for Snoozing

Mobile actions will be handled according to scheme, where the command is one of `SNOOZE`,`SILENCE` or `NORMAL`, recipient
type is one of `USER`,`EVERYONE`, and target type is one of `NONCRITICAL`,`EVERYTHING`,`TRANSPORT`,`DELIVERY`,`CAMERA`,`PRIORITY` or `MOBILE`.

The user is determined by matching the mobile device id in the event to the registry of mobile devices per
person in Supernotify, either manually configured or automatically discovered.

#### Action structure

`SUPERNOTIFY_<COMMAND>_<RecipientType>_<TargetType>`

#### Example action

```yaml
  event_type: mobile_app_notification_action
  data:
      action: SUPERNOTIFY_SNOOZE_USER_EVERYTHING
  origin: REMOTE
  time_fired: "2024-04-20T13:14:09.360708+00:00"
  context:
      id: 01HVXT93JGWEDW0KE57Z0X6Z1K
      parent_id: null
      user_id: e9dbae1a5abf44dbbad52ff85501bb17
```
