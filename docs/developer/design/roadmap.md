# Roadmap

See also [Principles](./principles.md) for what guides development.

## Home Assistant Version Compatibility

When the following versions meet the 6-month ago window for testing, here are the changes to make

### 2026.2

Remove Py3.13 compatibility and testing

### 2026.8

Switch from `voluptuous` to `probatio`

## Features

### Packages

See [Packages](./packages.md)

### Extended UI Configuration

Second and further phases identified at [ConfigFlow](./configflow_approach.md)

### AI Friendly

Make it easier for people to use an AI Agent to setup, maintain or debug notifications.


#### Register an LLM API.
HA's homeassistant.helpers.llm lets an integration register a tool set through async_register_api. A notify tool with delivery, scenario and target parameters would work for Assist conversation agents. It should also be reachable through HA's MCP server. Check the current API before committing to this. It is the only option here that makes Supernotify callable by agents, not just easier to configure.

#### Richer services.yaml descriptions.
Every field's description, example and selector are what an LLM sees when it discovers actions. Your memory notes already flag dynamic delivery and scenario dropdowns via async_set_service_schema. That would help agents as well, since they would see the real delivery names.

#### Structured errors and diagnostics.
Config validation errors that name the key and the valid options let an agent self-correct. diagnostics.py helps the same way.

### Configurable links for email

### Actions for email

### Rate limiting

Moving window quota per priority. Per delivery / scenario limits.

### Holiday support

Randomization for greetings and sounds.

### Miscellaneous

- Transport overrides for scenarios
- MQTT Publish action
- Time ranges for notifications

### Delivery Explanations

Better explain in the archived message, the basis on which any single delivery was added or suppressed, including if several methods selected it, and if the code that made the decision is felt to be in need of improvement.

### Inclusion Default

An advanced and very usable mode is to have all deliveries selected only explicitly/by scenario so nothing is notified unless asked for, rather than by
default everything. This works well to minimize noise. However it means every delivery has to have inclusion set to `scenario` or `explicit` manually - make an option in configflow UI to set a global default.

Sort out explicit/implicit/scenario. Two of these mean the same thing. There's a useful delivery mode which is effectively target driven - only consider the transport if there's a target that needs it. On other hand deliveries like Persistence that only make sense if explicit.

## Internal Improvements

The internals of the code get more complex and harder to debug over time as functionality added, so continual need to go back over and force it to be simpler, while maintaining all reasonable backward compatibility.

### Overhaul use of `data` in pipeline

`extra_data` (and the older nested `data` of `notify.supernotify`) is currently merged into the same `data` that carries delivery, target and scenario data, all the way to the transports. That has some side effects:

- Supernotify's own transports read their options from it, for example `matrix_format` or `chime_tune`, so it is not purely data for the underlying integration
- `priority`, `message_html`, `spoken_message`, `force_resend` and `timestamp` are taken out of it by the envelope, so a value meant for the target integration, such as a mobile app push's own `priority`, never reaches it
- some transports, such as email and the generic `ntfy` and `notify_events` handling, read `media` and `actions`
  from that data rather than from the notification's own, which needs checking against the top level `media`
  and `actions` used by `supernotify.notify`

The plan is for `extra_data` to be passed through untouched, with Supernotify's own transport options and fields kept apart from it. Generic `data` mapping other than `extra_data` should terminate as soon as action handled. This also means finding another home or some other way of separating the data elements picked up by Supernotify transports.

Consider simplifying or renaming the `data` section needed for `delivery` definitions and overrides. This could mean that the term `data` only ever appears at the top of an action notification, as Home Assistant standard, and nowhere else.

Overhaul the Envelope's use of pop and get to pick out data elements such as priority. For something like priority the order should be:

- Notification Level
  - Global defaults
  - Action Data
  - Scenarios
- Envelope Level
  - Target level overrides
  - Delivery Config level overrides
  - Delivery Action Data overrides

The `priority` on the action data would always win, _unless_ the action data also had a delivery override with a different priority. (Question - scenarios, deliveries etc should be able to override too, so does a delivery level config priority win over a notification level action priority? Probably should do so, and use delivery overrides in action to resolve that if the default behaviour doesn't suit)

#### Transport Usage of Extra Data

Its possible these are really the same thing as options, but lacking the documentation and passed a different way. Review and see if they can brought into the options setup, so there's automatic document generation for them, and they can be passed in `options` rather than `data`. Check if that completely removes Supernotify usage of `extra_data` and also review use of `options` from actions rather than static config.

(Analyzed for `v2.6.0-beta1`)

| Group                      | Keys                                                                                                                                     | Notes                                                                                                     |
|----------------------------|------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| Prefixed transport options | `chime_*`, `discord_*`, `gotify_*`, `html5_*`, `kodi_*`, `lametric_*`, `matrix_*`, `mobile_push_*`, `ntfy_*`, `pushover_*`, `telegram_*` | Removed by their transport, only the remainder reaches the integration                                    |
| Email                      | `template`, `footer`, `action_url`, `action_url_title`, `snapshot_url` (or `media.snapshot_url`)                                         | `template` and `footer` are Supernotify's own                                                             |
| Alexa Media Player         | `volume`, `type`, `pause_music`, `restore_volume`, `tts_char_speed`, `volume_fallback`, `wait_for_tts`                                   | Unprefixed                                                                                                |
| Chime                      | `chime_tune`, `chime_volume`, `chime_duration`, `enqueue`, `announce`                                                                    | `enqueue` and `announce` are `media_player` fields                                                        |
| Generic                    | `variables`, `value`, `media`, `actions`, `token`, `level`                                                                               | `token` and `level` are for `notify_events`; `media` and `actions` are also top level notification fields |
| MQTT and persistent        | `topic`, `payload`, `notification_id`                                                                                                    |                                                                                                           |
| TTS                        | `language`, `cache`, `options`, `media_stream`                                                                                           | Fields of `tts.speak` selected by the transport, so borderline pass-through                               |
| Handled by the envelope    | `priority`, `message_html`, `spoken_message`, `force_resend`, `timestamp`                                                                | Taken out before the transports see the data, never passed to integrations                                |

#### Other clean-up

Fields like `message_html`,`spoken_message`,`priority` are treated inconsistently across notification and envelope. some belong to both objects as attributes, some to just one.


### Per-delivery priority

Setting `priority` in a delivery, target or scenario `data` block changes the priority of just that delivery, for example to downgrade one channel while the rest stay at the call's priority. It works, but is not documented, and only affects what the transport sees. Delivery selection by priority, snoozing and scenario conditions still use the priority of the original call.

The plan is to make this a documented, supported setting, and decide which of those should follow it.

## Completed Roadmap

- [ConfigFlow](./configflow_approach.md)
   - v2.0.0
   - Partially completed, basic YAML only
- [Deliveries and Transports](./deliveries_and_transports.md)
   - v2.5.0
