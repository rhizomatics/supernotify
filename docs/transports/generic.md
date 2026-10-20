---
tags:
  - transport
  - generic
  - script
  - rest_command
  - light
  - siren
  - mqtt
  - input_text
  - ntfy
  - switch
  - sns
  - sqs
  - eventbridge
  - lambda
  - aws
  - notify
  - custom
  - notify_events
---
# Generic Transport Adaptor

| Transport ID | Source                                                                                                                                    | Requirements | Optional                                                    |
|--------------|-------------------------------------------------------------------------------------------------------------------------------------------|--------------|-------------------------------------------------------------|
| `generic`    | :material-github:[`generic.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/generic.py) | -            | *Any Home Assistant action from core or custom integration* |


Use this transport to call *any* action, including 'legacy' Notification actions (previously known in Home Assistant as 'service') and scripts, REST commands, or anything else Home Assistant can call. It can be used for simple calls, where all you need to do is plug in an action, or as a "toolbox" for more complex needs.

### Raw Mode

If you really want it to be a blank slate and override what it knows about domain rules, then use `raw: true` in the delivery `options` list. In raw mode, `message`, `title` and all `data` elements are passed as Action Data, along with all the targets in `target`, exactly as for the *default* row in [Known Integrations](#known-integrations), and no checking against the action's schema is made.

### Known Integration Mode

To make life easier, its not entirely a blank slate, and knows about the appropriate `data` sections for most of the common options - see [Known Integrations](#known-integrations) for more.

Outside of raw mode, the Action Data is checked against the schema the action declares, where it has one, and any fields the action doesn't accept are quietly dropped, so a `data` section can carry values meant for other deliveries without breaking this one.

!!! info
    This transport has also been used to add some minor support for an integration that doesn't yet warrant a full scale transport. For example, this was the case for [ntfy.sh](https://ntfy.sh) before the [ntfy transport](../transports/ntfy.md) was contributed, and remains the case for the [notify.events](https://notify.events) vendor service.

### Notify Actions

If an action is in the `notify` domain, then `message`,`title`,`target` and `data` will be passed in the Action (Service) Data.

```yaml title="Example Configuration"
delivery:
  chat_notify:
    transport: generic
    action: notify.custom_chat
```

Use this delivery with action calls like this:

```yaml title="Example Action Call"
    - action: supernotify.notify
      data:
        title: "My Home Notification"
        message: "Notify via custom chat"
        delivery:
            chat_notify:
                data:
                    channel: 3456
```

This includes support for [MQTT Notify Entities](https://www.home-assistant.io/integrations/notify.mqtt/). (Supernotify also offers an [MQTT Transport Adaptor](mqtt.md) for direct flexible access to `mqtt.publish`.)

### Selecting Targets

By default, Generic will throw all the targets applied in the configuration or action call at the notification, in one flat list of targets, or a single string value if only one target.

Usually you will want to be more specific. If the target is a common built-in type like `entity_id` or `email`, then specify this in the `target_categories` option.

```yaml
delivery:
  chat_notify:
    transport: generic
    action: notify.custom_chat
    options:
      target_categories: entity_id
```

If it's not a standard target type, then make one up. In this example, for personal Slack channels, which in this example is called "slack_channel" but can be anything you like so long as it matches up ( you could have separate categories for "slack_group_dm", "slack_user" etc)

```yaml title="Config Snippets"
recipients:
  - person: person.my_user
    delivery:
      slack:
        target:
           slack_channel: A20H2AN55DX
delivery:
  slack:
      transport: generic
      action: notify.my_slack_service
      options:
           target_categories: slack_channel
```

This can also be used in a notification call:

```yaml title="Example Action Call"
    - action: supernotify.notify
      data:
        message: "Notify via slack"
        target:
            slack_channel: "#JH838434"
```

### Known Integrations

Generic isn't completely a blank slate - it knows about the most common integration domains and will build a compatible Action call for them. These have a lot of variation because Home Assistant actions have a lot of variation! Generic Transports handling of these means you can create multi-channel notifications without worrying too much about the variety of `data` mappings etc.

Several of these now have their own transports, and are effectively deprecated in Generic although remain working - `ntfy`,`mqtt`,`siren` (`chime` transport),`tts` and `notify` (`notify_entity` transport).

| Domain                        | Action Data                                                                                                                                                 | Target Data             |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------|
| notify ( `send_message` only) | `message` and `title` only                                                                                                                                  | `entity_id` map         |
| notify ( other actions )      | `message` and `title` plus all `data` elements                                                                                                              | big list of all targets |
| input_text                    | `value` with message, or `value` from `data` if supplied                                                                                                    | `entity_id` map         |
| switch                        | Empty                                                                                                                                                       | `entity_id` map         |
| mqtt                          | All [permitted](https://www.home-assistant.io/integrations/mqtt/#action-mqttpublish) `data` elements. `payload` set to message value if not already defined | Empty                   |
| siren                         | All [permitted](https://www.home-assistant.io/integrations/siren/#action-sirenturn_on) `data` elements                                                      | `entity_id` map         |
| light                         | All [permitted](https://www.home-assistant.io/integrations/light/#action-lightturn_on) `data` elements                                                      | `entity_id` map         |
| rest_command | All of `data` | Empty |
| notify_events | All [permitted](https://www.home-assistant.io/integrations/notify_events#message-optional-parameters) `data` elements | Empty |
| ntfy (`ntfy.publish`) | **Deprecated**, use the [ntfy transport](ntfy.md), a repair issue is raised at start up. All [permitted](https://www.home-assistant.io/integrations/ntfy/#publish-notification) `data` elements. `snapshot_url` will be used for `attach` and `action_url` for `click`. A separate publish is made for each `email` or `call` target | `entity_id` map of `notify` domain targets (the ntfy topics), required |
| script (`turn_on` and `turn_off` only) | `variables` contains a mapping of `message`,`title` plus any `variables` items in `data`. Other `data` elements added in their own right  | `entity_id` map |
| script (script name as action) | `message` and `title` plus all `data` elements | Empty |
| tts (`speak`) | `message` plus all [permitted](https://www.home-assistant.io/integrations/tts/#action-speak) data elements. `media_player_entity_id` set from `media_player` targets, if not already in `data` | `entity_id` map of `tts` targets |
| tts (legacy `*_say` actions) | `message` plus all permitted data elements | `entity_id` map of `media_player` targets |
| *default* |  `message` and `title` plus all `data` elements | big list of all targets |

Where the Target Data is an `entity_id` map, only entities from that domain are passed (or from the domain set by `handle_as_domain`, as well as the action's own). If none of the targets match, the delivery is skipped rather than calling the action with no entities, which Home Assistant would quietly do nothing with.

!!! tip "Notify Events"
    `notify_events` has no definite action call in Home Assistant, so use `handle_as_domain: notify_events` in the `options` section of the *Delivery* configuration to switch on the special processing in Generic Transport, otherwise the same `data` section will be passed on as received in the action.

### Input Text Integration

`input_text` can be used with ESP32, APIs and similar to pass text.

Configure a delivery:

```yaml
delivery:
  esp_screen:
    transport: generic
    action: input_text.set_value
    target: input_text.my_esp32
```

The `message` value on the notification will be passed as the `value` on the `data` section. See [Input Text Integration](https://www.home-assistant.io/integrations/input_text/) for more on that.

### Other Actions

For the `switch`, `siren`, `light`, `mqtt` and `rest_command` domains, the `data` supplied will be passed directly as the Action Data, and message and title dropped as likely to be a problem for those integrations. Any other action not in the [Known Integrations](#known-integrations) table gets the *default* handling, of `message`, `title` and all `data` elements, with all the targets.

If you have an action that is not supported, but it requires a similar Home Assistant Action call as one it does support, then the `handle_as_domain` option can be used.

```yaml
delivery:
  light_flasher:
    transport: generic
    action: flashywashy.flash_me_now
    options:
      handle_as_domain: light
```

Entities targeted are those in the action's own domain, here `flashywashy`, and those in the domain it's handled as, here `light`.

Alternatively, if the custom action call is failing because of `data` elements from the notification it can't handle, you can control which keys are included, in this example, all keys that don't match the pattern will be dropped (test is made using Python's `re.fullmatch`):

```yaml
delivery:
  zigzag:
    transport: generic
    action: zigzag.zig
    options:
      data_keys_select:
        - enabled
        - value
        - zig.*
```

This can be more explicitly expressed with an `include` block, the shortcut style is simpler to edit and read but only works when including a simple flat list.

```yaml
delivery:
  zigzag:
    transport: generic
    action: zigzag.zig
    options:
      data_keys_select:
        include:
          - enabled
          - value
          - zig.*
```

It also works the other way round, or indeed both together, with excluding, so all `data` keys are passed, except selected ones:

```yaml
delivery:
  zigzag:
    transport: generic
    action: zigzag.zig
    options:
      data_keys_select:
        exclude:
          - duration
          - volume
```

Nested dicts (such as the `data:` block inside a Home Assistant notification `data:` section) can also be filtered at arbitrary depth. When `exclude` is a mapping, a null value excludes that key; a dict value keeps the key but recurses into it with the same tree logic:

```yaml
delivery:
  mobile_notify:
    transport: generic
    action: notify.mobile_app_my_phone
    options:
      data_keys_select:
        exclude:
          data:             # descend into `data`
            attachment:     # exclude `attachment` from `data`
            video:          # exclude `video` from `data`
            media:          # descend into `data.media`
              url:          # exclude `url` from `data.media`
```

**Named sub-filter** — any non-reserved key in the config dict is a full `data_keys_select` config applied recursively to that key's value:

```yaml
    data_keys_select:
      include: [message, data]      # top-level include
      data:                         # sub-filter for `data`
        include: [attachment, push]
```

Both forms can be combined freely and nest to any depth.

!!! tip
    If using Generic to trigger bells, sirens or other noises, consider the [Chime Transport Adaptor](chime.md), which makes that easier, especially if working with a mix of audio devices. It has a similar set of known integrations, geared towards sounds rather than messages.

### AWS

See the core [AWS Integration](https://www.home-assistant.io/integrations/aws/) for how to
use notify to send messages to AWS Lambda, SNS, SQS and EventBridge.

## Discovery

**Not auto-detected, unless an `action` is set at transport level.**

Generic is a catch-all for user-defined actions, so there's nothing for Supernotify to discover on its own — either set `action:` under `transports: generic: delivery_defaults:` (from which a `generic` delivery is generated automatically once selected), or add a `generic` delivery of your own with your chosen `action:` directly.
