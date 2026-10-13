---
tags:
  - actionable_notifications
  - action
  - mobile_push
  - action_groups
description: How Actionable Notification buttons (Mobile Actions) and reusable Action Groups work
---

# Mobile Actions and Action Groups

!!! note
    This page is about the buttons on an [Actionable Notification](https://companion.home-assistant.io/docs/notifications/actionable-notifications/)
    (referred to throughout as **Mobile Actions**), not Home Assistant *Actions* (previously known as 'services') such as `supernotify.notify` - those are documented at [Actions](actions.md).

Mobile Actions as buttons currently only affect the [Mobile Push](../transports/mobile_push.md) transport - other transports either ignore `actions`/`action_groups` entirely, or only pick up the single `action_url` link described below. A [notification level action](#notification-level-actions), which is what tapping the notification itself opens, also works for ntfy, Gotify and HTML5.

!!! note
    Don't confuse `action_groups:` here with [`mobile_push_group`](../transports/mobile_push.md#notification-grouping) - that's an unrelated Companion App feature for visually stacking notifications together, named `group` for consistency with the Companion App's own docs even though it clashes with "action groups" here.

## Ad-hoc actions on a single notification

Add an `actions` list directly to the `data:` of a notify call. Each entry maps almost directly onto the [Home Assistant Mobile App Actions](https://companion.home-assistant.io/docs/notifications/actionable-notifications/):

```yaml title="Ad-hoc mobile action"
- action: supernotify.notify
  data:
    message: Garage door has been open for 10 minutes
    actions:
      - action: CLOSE_GARAGE_DOOR
        title: Close it
        icon: "sfsymbols:door.garage.closed"
```

Recognized fields per action:

| Field                       | Notes                                                                                       |
|------------------------------|-----------------------------------------------------------------------------------------------|
| `action`                    | Required to make a real button - the identifier delivered back on `mobile_app_notification_action` |
| `title`                     | Button label                                                                                   |
| `action_url`                | A URL (relative URLs are resolved against your HA external/internal URL)                       |
| `action_url_title`          | Optional explicit title for `action_url` - see [Auto-fetched link titles](#auto-fetched-link-titles) below |
| `level`                     | `action` for a button, which is the default, or `notification` for a [notification level action](#notification-level-actions) |
| anything else (`icon`, `uri`, `destructive`, `behavior`, `textInputButtonTitle`, `textInputPlaceholder`, `activationMode`, `authenticationRequired`, ...) | Passed straight through to the Companion App - see its [action fields reference](https://companion.home-assistant.io/docs/notifications/actionable-notifications/#building-notifications-with-actions) |


## Action Groups

Ad-hoc actions are fine for a one-off, but most actionable notifications are reused across many
notifications (arm/disarm buttons, camera snooze, etc). Define them once under the top-level
`action_groups:` YAML key, then attach them by name.

```yaml title="Config: define reusable groups"
action_groups:
  alarm_panel_disarm:
    - action: ALARM_PANEL_DISARM
      title: Disarm Alarm Panel
      icon: "sfsymbols:bell.slash"
  alarm_panel_reset:
    - action: ALARM_PANEL_RESET
      title: Arm Alarm Panel for at Home
      icon: "sfsymbols:bell"
```

Each group is a list of the same action objects described above (`action`/`title` plus any extra
Companion App fields). `action_template`, `title_template` and `uri_template` can be used in place of
`action`, `title` and `uri`, and are rendered for each notification, with the same variables as
[scenario conditions](../configuration/scenarios.md), such as `notification_priority`, `notification_message` and `camera`.

```yaml title="Config: templated action"
action_groups:
  priority_actions:
    - action_template: "SILENCE_{{ notification_priority | upper }}"
      title_template: "Silence {{ notification_priority }} priority notifications"
      uri_template: "https://my.home/alerts/{{ notification_priority }}"
```

### Attaching groups to a notification

```yaml title="Notify call referencing a group"
- action: supernotify.notify
  data:
    message: Someone is at the front door
    action_groups:
      - alarm_panel_disarm
```

`action_groups` in a notify call is a list of group *names*. Only those named groups' actions are added.

### Attaching groups from a scenario

More commonly, a [Scenario](../configuration/scenarios.md) attaches the group instead, so the right buttons appear automatically depending on state, without every automation having to know about them:

```yaml title="Scenario-driven groups"
scenarios:
  alarm_armed:
    conditions:
      - condition: state
        entity_id: alarm_control_panel.home_alarm
        state: [armed_home, armed_night, armed_away]
    action_groups:
      - alarm_panel_disarm
      - alarm_panel_reset
```

Groups from every currently-enabled scenario are unioned together with any explicit `action_groups` on the call itself.

!!! info "There's no implicit &quot;all groups&quot; default"
    It might look, from the transport code, like omitting `action_groups` entirely means "use every configured group" - but in practice a plain notification (no matching scenario, no explicit `action_groups:` in the call) ends up with **no** group actions attached at all. An empty `action_groups: []` on the call behaves the same as omitting it: scenarios can still add groups on top. To guarantee no group actions ever appear on a given notification, don't enable a scenario that adds them.

A scenario referencing a group name that isn't defined under the top-level `action_groups:` is dropped at startup with a logged error and a repair issue, rather than failing to load.

## Notification level actions

An action with `level: notification` isn't a button, it's what opens when the notification itself is tapped. It must have a `uri` or `uri_template`, can't have an `action`, and there can only be one in an action group, or in the `actions` of a notification.

```yaml title="Config: open the cameras dashboard when the notification is tapped"
action_groups:
  camera_actions:
    - action: CAMERA_SILENCE
      title: Silence
    - level: notification
      uri: homeassistant://navigate/lovelace/cameras
```

```yaml title="Ad-hoc notification level action"
- action: supernotify.notify
  data:
    message: Garage door has been open for 10 minutes
    actions:
      - level: notification
        uri: /lovelace/garage
```

| Transport                                     | Sent as                                                       |
|-----------------------------------------------|---------------------------------------------------------------|
| [Mobile Push](../transports/mobile_push.md)   | `url` for iOS and `clickAction` for Android, unless one is already in the `data` |
| [ntfy](../transports/ntfy.md)                 | `click`, unless there's an `ntfy_click`                       |
| [Gotify](../transports/gotify.md)             | The click url, unless there's a `gotify_click`                |
| [HTML5](../transports/html5.md)               | `url`, unless there's an `html5_url` or a `url` in `html5_data` |

A path such as `/lovelace/garage` opens in the Companion App for Mobile Push, and is made into a full Home Assistant URL for the other transports.

Where a notification ends up with more than one, only one is used, in this order:

1. One in the `actions` of the notification
2. One in the `action_groups` of the notification, in the order listed
3. One in the action groups of a scenario, the first scenario winning

## Snoozing from a Mobile Action

When a notification includes `media.camera_entity_id`, Supernotify automatically appends one more
action - `SUPERNOTIFY_SNOOZE_EVERYONE_CAMERA_<camera_entity_id>` - with a text-input prompt for
minutes to snooze. This, and the wider `SUPERNOTIFY_<COMMAND>_<RecipientType>_<TargetType>` action
naming scheme that Supernotify listens for on `mobile_app_notification_action` events, is covered in full on the [Snoozing](snoozing.md) page - you don't need to wire up your own automation for it.

## Auto-fetched link titles

If an action (ad-hoc or from a group) has `action_url` set but no `action_url_title`, Mobile Push will fetch the page at that URL and use its HTML `<title>` as `action_url_title`. Titles are cached per-URL for the life of the transport; a failed fetch is not retried for 15 minutes. This never affects whether the button appears - it only adds metadata to the action object.

## References

- [Companion App: Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/)
- [Mobile Push transport](../transports/mobile_push.md)
- [Scenarios](../configuration/scenarios.md)
- [Snoozing](snoozing.md)
- [Actions (services)](actions.md)
