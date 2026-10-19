# RFC 0006: Frigate Auto Notifier

2026-09-24 · Jey Burrows · Status: draft

## Summary

One of the first [Auto Notifiers](./0003-auto_notifier.md): a new module (with optional separate HACS custom component for visibility) that replaces the
[Frigate Notifications blueprint](https://github.com/SgtBatten/HA_blueprints/tree/main/Frigate_Camera_Notifications)
(beta `0.14.0.3l`) for review events, sending everything through Supernotify.

## Goals

- 100% ConfigFlow, no YAML needed to set up or use
- Sensible defaults, autoselects cameras
  - Users delete cameras they don't want rather than add ones they do
  - If supernotify setup gets working mobile, email and voice notifications
  - Same fallback as `appliance_autonotify` without supernotify, call all mobiles
- Every part of the `supernotify.notify` call can still be tuned, using the same UI as an automation action
- Supernotify's own YAML still applies, so users can add scenarios or deliveries that react to Frigate notifications
- The [Apple push fix](../../recipes/fix_frigate_apple_push.md) is built in, with an option to turn it off
- Use the new notification level click thru for a destination URL
- All AutoNotify components should look and behave similarly
- Garner feedback on changes for Supernotify
  - See [Principle 12](../principles.md) on building out mobile support
  - Primary goal is to enhance Supernotify such that automations and blueprints *like* the Frigate one don't require 100s of lines of YAML to handle different phone models, notification options
- Design for HomeAssistant and Frigate rather than blindly following the Frigate blueprint
  - https://docs.frigate.video/integrations/home-assistant/ is canonical
  - https://docs.frigate.video/configuration/notifications may offer suggestions of what's needed to handle
- Works with standalone Frigate or running as a HA app

Out of scope for the first release:
 - GenAI review summaries (`frigate/tracked_object_update` and the `genai` review type),
 - ANPR
 - Telegram inline keyboards
 - Android TV overlays.
 - Telegram and TV remain possible as ordinary Supernotify deliveries.

## Architecture

New HACS component, **Frigate AutoNotify**

Has dependencies on the Frigate and MQTT integrations. Supernotify is an 'after' dependency, so not required for startup. Possibly Frigate Proxy can be optional too.

- **Config subentry per camera**
- **Config subentry for all cameras** - Set auto-discovery, like Appliance AutoNotify. Use for any global defaults
- **Frigate settings discovered** from the existing `frigate` config entry. The MQTT topic prefix, proxy client ID and
  base URL are read from the Frigate entry and Home Assistant's external URL, replacing the blueprint's `base_url`,
  `client_id` and `mqtt_topic` inputs.
  If no Frigate proxy, use default mqtt topic
- **Runtime**: one MQTT subscription per entry; a review tracker keeps per-review state (severity, objects,
  sub-labels, zones, last sent) in memory, replacing the blueprint's `wait_for_trigger` loop. Everything is in code,
  so improvements reach existing users on upgrade

## Customization UI

Offer same notification options and integration as Appliance AutoNotify.

## Reference

Frigate blueprint variables.

| Variable                                       | Meaning                                                                     |
| ---------------------------------------------- | --------------------------------------------------------------------------- |
| `camera`, `camera_name`, `camera_entity_id`    | Frigate camera name, title-cased name, and its HA camera entity             |
| `label`, `objects`, `sub_labels`               | Formatted label (with sub-labels merged, as the blueprint does), raw lists  |
| `zones`, `severity`, `review_id`, `detection_id` | From the review payload                                                   |
| `snapshot_url`, `thumbnail_url`, `clip_url`, `hls_url`, `review_url` | Pre-built proxy URLs, so users don't need to know the API paths |
| `is_update`, `is_final`, `update_reason`       | Whether this is a follow-up for the same review, and why it was sent        |

Filters stay as structured fields, not templates:

| Blueprint input                                   | Profile setting                                                         |
| ------------------------------------------------- | ----------------------------------------------------------------------- |
| `camera`                                          | Multi-select of Frigate cameras                                          |
| `review_severity`                                 | Alert / detection                                                        |
| `labels`, `zones`, `zone_multi`, `zone_order_enforced` | Selects populated from the Frigate config for the chosen cameras     |
| `presence_filter`                                 | Person/zone entity select - or leave to Supernotify occupancy scenarios |
| `state_filter`, `state_entity`, `state_filter_states`, `disable_times`, `master_condition`, `custom_filter` | One `ConditionSelector`, pre-filled empty |
| `cooldown`, `timeout`, `initial_delay`, `final_delay`, `final_update`, `alert_once` | Number and boolean fields in an *Advanced* section   |
| `update_sub_label`                                | Boolean                                                                  |

Delivery-level inputs from the blueprint are **not** profile settings, because Supernotify already owns them:

| Blueprint input                                   | Where it lives instead                                                   |
| ------------------------------------------------- | ----------------------------------------------------------------------- |
| `notify_device`, `notify_group`                   | Supernotify recipients and mobile push delivery - fixes the blueprint's notify group problems |
| `critical`, `interruption_level`, `sound`, `volume` | `priority` in the action, mapped by the mobile push transport            |
| `color`, `icon`, `sticky`, `channel`, `android_auto`, `subtitle` | `extra_data` in the action; `mobile_push_*` options where they exist |
| `group`, `tag`                                    | Set by the component from camera and review ID                          |
| `attachment`, `attachment_2`, `video`, `ios_live_view` | `media` in the action (`snapshot_url`, `clip_url`, `camera_entity_id`) |
| `tap_action`, `button_1..3`, `url_1..3`, `icon_1..3` | `actions` in the action, default *View Clip* and *View Snapshot*       |
| `button_3` silence, `silence_timer`               | Supernotify's own camera snooze action                                   |
| `tts`, `tts_helper`                               | A TTS delivery, or `mobile_push_tts_text`; dedupe per review is component state |
| `custom_action_manual`, `custom_action_auto(_multi)` | Extra actions in the stored action sequence; manual ones via a component action button |
| `telegram_*`, `tv_*`                              | Ordinary Supernotify deliveries, later                                   |
| `debug`, `redacted`                               | Supernotify archive and debug trace                                      |

Remaining profile settings, with the fix recipe:

- **Apple-compatible video links** (default on) - Apple devices get the HLS `master.m3u8` link and no `clip.mp4`
  attachment or `clickAction`, as in the [recipe](../../recipes/fix_frigate_apple_push.md). Off sends the same links to
  every device, as the blueprint does

## Changes needed in Supernotify

See [Auto Notifier Support](./0003a-auto_notifier_support.md), which covers these for all packages. For Frigate, the essentials are snooze enforcement, notification source, lifecycle and tag, cooldown, and the mobile push media, iOS video, tap URL and live view changes.

## Open Questions

- Spike: confirm `ConditionSelector` renders in config flows, since no core integration uses it there yet
- How does the component know Frigate's camera list, zones and labels during the flow - from the Frigate integration's
  coordinator data, or the Frigate API?
- Some type of 'entity context' needed here rather than context as calling automation/trigger
  - Appliance AutoNotify would have that too, i.e. the washing machine, or by proxy the power monitor for it
- Is there too much variation for a simple `apply-scenarios` approach? does this need to supply new variables to drive downstream conditions?
- Live activities for view, or click thru?
