# Snoozing

Source: https://supernotify.rhizomatics.org.uk/latest/usage/snoozing/

Snoozing can be selected from a mobile action, and made for a set time, or notifications can be silenced until further notice. Snoozes are persisted to Home Assistant's integration storage, so will be reactivated after Home Assistant restarts, and included in backups.

Three Home Assistant actions (previously known as "services") are available to manage snoozes:

- `supernotify.snooze`
- `supernotify.clear_snoozes`
- `supernotify.enquire_snoozes`

### Snoozing from a script or dashboard

`supernotify.snooze` makes the same snoozes as a mobile action, a voice sentence or the AI tool, from an automation, a script or a dashboard button. Any user can call it, while firing the mobile action event through the API needs an admin.

```yaml
action: supernotify.snooze
data:
  command: snooze          # snooze, silence (until resumed) or resume
  scope: delivery          # everything (default), noncritical, delivery, transport, priority, camera or tag
  name: alexa_announce     # the delivery, transport, priority, camera entity_id or tag, for those scopes
  person: person.alice     # only this person's notifications; everyone if left out
  minutes: 30              # snooze only; the configured snooze time if left out
  reason: Dashboard        # shown by enquire_snoozes
```

With a response requested, it returns the snoozes now active, as `enquire_snoozes` does. `resume` removes the snooze with the same scope, name and person.

Snooze context is also logged in the debug trace, which can be archived to the file system or MQTT topic.

### Snoozing by Tag

A `TAG` snooze covers every notification that a word or name like *driveway* applies to. It matches if the tag is:

- the name of one of the notification's scenarios, whether applied by the automation or selected by its conditions
- the `entity_id`, object_id, friendly name or an alias of the entity in the notification's `entity_id` data, as the Frigate blueprint sends, or of its `media` camera
- the object_id then the domain, so *driveway camera* matches `camera.driveway`

Case, underscores and extra spaces are ignored, so *unknown vehicle* matches the `unknown_vehicle` scenario. The tag is matched as each notification is sent, so if a scenario and a camera are both called *driveway*, both are covered.

Tag snoozes can be made by voice, see [Built-in Agent Sentences](https://supernotify.rhizomatics.org.uk/latest/usage/assist/#built-in-agent-sentences), by an AI agent, or with a mobile action like `SUPERNOTIFY_SNOOZE_USER_TAG_driveway`.

### Mobile Actions for Snoozing

Mobile actions will be handled according to scheme, where the command is one of `SNOOZE`,`SILENCE` or `NORMAL`, recipient type is one of `USER`,`EVERYONE`, and target type is one of `NONCRITICAL`,`EVERYTHING`,`TRANSPORT`,`DELIVERY`,`CAMERA`,`PRIORITY`,`MOBILE` or `TAG`.

The user is determined by matching the mobile device id in the event to the registry of mobile devices per person in Supernotify, either manually configured or automatically discovered.

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
      user_id: a9dbae1a5abf33dbbad52ff82201bb17
```
