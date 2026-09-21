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

Mobile Actions currently only affect the [Mobile Push](../transports/mobile_push.md) transport - other transports either ignore `actions`/`action_groups` entirely, or only pick up the single `action_url` link described below.

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
Companion App fields). There's also an `action_template`/`title_template` pair in the schema for a
templated `action`/`title` - **these are currently accepted but never rendered**, so the literal
`{{ ... }}` template text would be sent to the app. Stick to plain `action`/`title` for now.

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

More commonly, a [Scenario](../configuration/scenarios.md) attaches the group instead, so the right buttons appear
automatically depending on state, without every automation having to know about them:

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
