# Roadmap

See also [Principles](./principles.md) for what guides development.

## Feedback

[Github Discussion #202](https://github.com/rhizomatics/supernotify/discussions/202)


## Home Assistant Version Compatibility

When the following versions fall out of the 6-month ago window for testing, here are the changes to make

### 2026.2

Remove Py3.13 compatibility and testing
Pillow >=12.1 - switch to get_flattened_data

### 2026.8

Switch from `voluptuous` to `probatio`

## Notification Features

### Rate Limiting

Moving window quota per priority. Per delivery / scenario limits.

### Time Ranges

Time ranges for notifications.
 - See [Supernotify Bands Card](https://github.com/lollox80/supernotify-cards/blob/main/README.md#supernotify-bands-card)

### Per-delivery Priority

Setting `priority` in a delivery, target or scenario `data` block changes the priority of just that delivery, for example to downgrade one channel while the rest stay at the call's priority. It works, but is not documented, and only affects what the transport sees. Delivery selection by priority, snoozing and scenario conditions still use the priority of the original call.

The plan is to make this a documented, supported setting, and decide which of those should follow it. See also the priority ordering in [Overhaul use of `data` in pipeline](#overhaul-use-of-data-in-pipeline).

### Holiday Support

Randomization for greetings and sounds. Sleigh bells are nice on first notification, annoying after that if every announcement has same one.

### Other Features

- Transport overrides for scenarios
  - Selecting by transport rather than by name.
    - Patterns only work if deliveries follow a naming convention. A scenario can't say "every delivery using the email transport", so user-named deliveries like plain_email, html_email and alerts_to_sue are only caught by luck. One option is a key such as transport: email, or a transport:email prefix, resolved against Delivery.transport.name.
  - Overriding more than enabled, target and data (see also ideas on `data` improvements)
    - A scenario can't change the delivery or transport settings that matter most in a scenario:
    - options (for example target_select, message formatting, chime tune mappings)
    - the delivery's priority filter
    - target_usage
    - selection_rank
  - Switching a whole transport off.
    - Today this means a delivery pattern with enabled: false, which fails the same way as in point 1. The alternative is the transport's own switch, but that's global, not per scenario.

## Transports

### Alexa Media Player

- Support notify entities directly, so they get similar benefit of spoken notification tweaks. This would mean the transport is partly implicit, and partly explicit (media_player)

### Chime

- Chime Aliases should be targets in their own right, so a target list could call chime:doorbells.
  - Possibly chime aliases should be able to have labels, areas etc and probably they are really Notify Entities and wouldn't suffer from the paucity of functionality offered by those

### Email

#### HTML Email

Revisit the HTML template, review if more than 1 needed, and ways to make it more useful in bringing HA context into a notification

## Delivery and Target Selection

### Inclusion Default

An advanced and very usable mode is to have all deliveries selected only explicitly/by scenario so nothing is notified unless asked for, rather than by
default everything. This works well to minimize noise. However it means every delivery has to have inclusion set to `scenario` or `explicit` manually - make an option in configflow UI to set a global default.

Sort out explicit/implicit/scenario. Two of these mean the same thing. There's a useful delivery mode which is effectively target driven - only consider the transport if there's a target that needs it. On other hand deliveries like Persistence that only make sense if explicit.

### Target-Driven Implicit Selection

Today, whether a delivery is an implicit selection candidate (`select_deliveries()`) is decided purely by its static `inclusion: default` config, independent of what target was actually given in the call. `email`/`mobile_push`/`notify_entity`/`html5`/`alexa_devices` happen to be `default`, so giving a bare email address or a `notify.*` entity in `target:` "just works" without naming a delivery - but that's really an accident of those specific transports also being default-inclusion, not a real target-matching mechanism. A transport like Discord is `explicit`-only, so even a fully-qualified `target: {discord_channel: "x"}` (which by itself unambiguously identifies the category - see `Transport.target_categories`) goes nowhere unless the call *also* names the delivery explicitly. The value doesn't error - it just sits unclaimed, visible only via `unassigned_targets` in the archive.

The real fix: drive implicit selection directly off target generation - any delivery whose `target_categories` can definitively (unambiguously, by shape) match something in the given target should be an implicit candidate, unless otherwise disabled, regardless of its static `inclusion` setting. This makes email and Discord symmetric, and gives `default`/`explicit` its narrower, original meaning back (should this fire when nothing in the target specifically calls for it).

This has a real circular-dependency complication to solve: a delivery with its own **fixed** target - e.g. a permanent archive/BCC email address configured directly on the delivery, not derived from any recipient or call-supplied target - has no target to match *until* it's already selected, and under a pure target-driven model there'd be nothing to trigger its selection in the first place. Whatever design replaces today's static `inclusion` flag needs an explicit carve-out for this case (a delivery can declare itself a candidate independent of the notification's target, the way `inclusion: default` does today) - it can't be *purely* target-driven.

Implemented as a stopgap in the meantime: `discord` and `matrix` are now `inclusion: default` too. Their values (a channel ID, a room alias) can't be auto-detected from a bare, untyped string - that's a different concern, about shape-matching an unqualified value - but once explicitly qualified with their own dedicated category key (`discord_channel:`, `matrix_room:`, none shared with any other transport), there's no ambiguity about which delivery a value belongs to, so they're exactly as safe as email/mobile_push already are.

`mqtt` was reverted back to `explicit` after initially being included in this stopgap: `topic` is just as dedicated a category as `discord_channel`/`matrix_room`, but `target_required` is `optional`, not `always`, because a topic can legitimately be given as a `data:` keyword instead of a target (a delivery with a fixed topic baked into its own config, needing no target at all). That means `NO_TARGET` never short-circuits it the way it does for Discord/Matrix, so there's no cheap way to tell up front whether a given notification is even relevant - defaulting it would mean a `deliver()` attempt, and its "No topic for publication" warning, on every single notification regardless of relevance. Fixing this properly needs the same target-driven design as the ambiguous transports below, not just a flip to `default`.

`kodi`, the generic `media` transport, `tts` and `alexa_media_player` are deliberately left out of this stopgap too. Their shared category is a bare `media_player` domain (`alexa_media_player`'s is platform-restricted, but still just "a media_player entity"), which is ambiguous in a different way to Discord/Matrix: even with only one transport claiming it, a `media_player.x` entity alone doesn't say whether the intent was an image, a sound, speech, or Kodi's own playback - there's no reliable way to pick the right operation from the entity alone, regardless of cross-delivery collision (`OPTION_UNIQUE_TARGETS`, off by default - `selection_rank` alone only orders processing, it doesn't stop a later delivery claiming a value an earlier one already took). That needs the fuller target-driven design above, not just a flip to `default`. `alexa_media_player` also doesn't yet handle the `notify.*`-entity form Alexa Media Player can expose, alongside its `media_player.*` one.

Chime has a related problem one level down: it currently matches `switch`/`media_player`/`siren`/`script`/`rest_command` entities directly, borrowing other domains' shapes, rather than through its own named chime aliases. A further step is to make chime aliases into targets in their own right, so a chime delivery can be matched unambiguously by alias name instead.

Consider also typed dict, or classes, for the deliveries mapping carried around inside Notification so easier to verify by type the interactions across functions.

## Setup and Configuration

### Extended UI Configuration

Second and further phases identified at [ConfigFlow](./rfcs/configflow_approach.md)

### Respond to Dynamic Home Assistant Changes

Listen out for changes to users, persons, integrations and change integrations

- User account added, auto-discover incl mobile devices
- Integration added, reassess viability and add if so ( or remove if integration no longer available )
- Same code running at supernotify startup and on listen events so consistent behaviour

## Observability

### Delivery Explanations

Better explain in the archived message, the basis on which any single delivery was added or suppressed, including if several methods selected it, and if the code that made the decision is felt to be in need of improvement. `delivery_provenance` (v2.8.0) now records which source enabled or disabled each delivery; suppression reasons and multiple selectors are still to do.

### Error Handling

Dead letter queue for failed deliveries, so admin can get by email if preferred, with options to throttle / group / summarize

Similar to above but for cases where delivery went ahead with errors, like mis-configured delivery or unknown scenario.

### Telemetry

- HACS may get included in basic stats
- Current downloads mix direct downloads and clones - https://rhizomatics.github.io/hacs-downloads/
  - See also extracted core version support data - https://claude.ai/artifact/7aGj3qD4uJXa8g3MFvuvNx
- No obvious way to find out which transport or features are used, other than HA stats on underlying transport usage, e.g. hardly anyone uses SMTP

## Ecosystem

### Packages

See [Packages](./rfcs/packages.md), starting with [Frigate SuperNotifier](./rfcs/frigate_supernotifier.md). The Supernotify changes needed first are in [Package Support](./rfcs/package_support.md).

### UI

There must be a better way of sharing dashboards than manual copy and paste of YAML from the [dashboard recipe](../recipes/notification_dashboard.md)

SignalK has nice idea of having recommended plugins, could be feature PR for HACS

### Extensibility

- Other developers able to create add-ons, see also [Packages](./rfcs/packages.md)
- Notification plugins could expose themselves directly as Transports so no additional development or release needed for Supernotify
- Consider moving Generic transport to its own notification toolbox plugin

### AI Friendly

Make it easier for people to use an AI Agent to setup, maintain or debug notifications.

v2.10.0 shipped a first beta, see [Assist and AI Agents](../usage/assist.md). It's all switched on in the options, on the **Assist and AI agents** page, and off by default.

- **LLM tools** (`llm.py`) for conversation agents that use an AI model, and so for HA's MCP server. Action
  tools send and snooze. Diagnostic tools explain recent notifications, dry run a notification, list
  snoozes, and look up the documentation site (`llms-full.txt`, fetched at most daily).
- **Built-in agent sentences** (`sentences.py`) for the agent without AI, registered as conversation triggers: notify someone or everyone, snooze, silence, resume, and ask for the last notification.
- **Notify action descriptions**: examples on the fields, the scenario fields as dropdowns of the configured scenarios, and the configured deliveries as the delivery field's example.
- **Errors**: unknown delivery and scenario names in a call are logged with the configured names and kept as `unknown_names` in the archive. Repair issues list what's configured and include condition errors, and diagnostics include open issues.

Still to do:

- Gather beta feedback on how well agents choose and fill in the tools, and how often the sentences are understood, then decide what to keep and whether to leave beta.
- The `llm` platform arrived after HA 2026.2 (missing there, present in 2026.9), so on older HA, still
  allowed by the `hacs.json` minimum of 2025.12.2, the tools just don't appear. Pin down the release and
  say so in the docs. `test_llm.py` is skipped on the older HA used for py3.13, until py3.13 is dropped.
- Sentences in other languages, registered for the language being spoken. Each needs wording from a native speaker, and the replies translated too.
- More sentences, if the feedback asks for them, such as snoozing one delivery or camera.
- The help tool searches the latest documentation, which can differ from the installed release. mike
  already publishes each release's docs under `/vX.Y.Z/`, so the tool could try the installed version
  first, and fall back to the latest when that release has no docs of its own.
- An agent can explain and test notifications, but not help set up Supernotify, since deliveries,
  scenarios and recipients are still YAML. A tool to check proposed YAML against the published JSON
  schemas would let an agent draft configuration safely. Packages with config flows reduce the need.
- The delivery field stays a free-form object, since it also takes a mapping that tunes deliveries. A
  dropdown would push that form into YAML.

## Internal Improvements

The internals of the code get more complex and harder to debug over time as functionality added, so continual need to go back over and force it to be simpler, while maintaining all reasonable backward compatibility.

### Overhaul use of `data` in pipeline

`extra_data` (and the older nested `data` of `notify.supernotify`) is currently merged into the same `data` that carries delivery, target and scenario data, all the way to the transports. That has some side effects:

- Supernotify's own transports read their options from it, for example `matrix_format` or `chime_tune`, so it is not purely data for the underlying integration
- `priority`, `message_html`, `spoken_message`, `force_resend` and `timestamp` are taken out of it by the envelope, so a value meant for the target integration, such as a mobile app push's own `priority`, never reaches it
- some transports, such as email and the generic `ntfy` and `notify_events` handling, read `media` and `actions`
  from that data rather than from the notification's own, which needs checking against the top level `media`
  and `actions` used by `supernotify.notify`

The plan is for `extra_data` to be passed through untouched, with Supernotify's own transport options and fields kept apart from it. Generic `data` mapping other than `extra_data` should terminate as soon as action handled. This also means finding another home or some other way of separating the data elements picked up by Supernotify transports. See also ideas on [extending options](#transport-usage-of-extra-data).

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

#### Other clean-up

Fields like `message_html`,`spoken_message`,`priority` are treated inconsistently across notification and envelope. some belong to both objects as attributes, some to just one.

## Completed Roadmap

- [ConfigFlow](./rfcs/configflow_approach.md)
   - v2.0.0
   - Partially completed, basic YAML only
- [Deliveries and Transports](./rfcs/deliveries_and_transports.md)
   - v2.5.0
- Delivery provenance in the archive, the first part of [Delivery Explanations](#delivery-explanations)
   - v2.8.0
- Area, floor and label targets, expanded before envelope generation with dupes resolved
   - v2.9.0
   - [https://github.com/rhizomatics/supernotify/pull/188]
- MQTT Publish action

## Rejected Roadmap

### Native Area, Floor and Label Targets

Area, floor and label targets are always resolved to entities before any transport sees them. Support transports that understand them natively as an exception, rather than relying on `extra_data`.

No existing standard Home Assistant integrations do this, so its an edge case that can be handled by `extra_data` fine. Reconsider if that ever changes, though its likely that all 'well-behaved' Home Assistant integrations will continue to let the platform resolve these entity selectors.
