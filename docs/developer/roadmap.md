# Roadmap

See also [Principles](./principles.md) for what guides development.

## Feedback

[Github Discussion #202](https://github.com/rhizomatics/supernotify/discussions/202)


## Home Assistant Version Compatibility

When the following versions fall out of the 6-month ago window for testing, here are the changes to make

### 2026.2

Remove Py3.13 compatibility - testing dropped with the 2026.10 release, code workarounds such as `RecipientNotifyEntity` left for a cooling off period
Pillow >=12.1 - switch to get_flattened_data

### 2026.8

Switch from `voluptuous` to `probatio`

## Other Migration Cleanup

### v1.9.0

- Delivery
  - `target_include_re`
  - `data_keys_include_re`
  - `data_keys_exclude_re`
- Transport
  - `device_discovery`
  - `device_domain"
  - `device_model_include`
  - `device_model_exclude`

### v2.5.0
- Delivery
  - `selection`

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

### Telegram

Add a target category to allow auto inclusion

### Alert

Review integration with `alert` - align live activities where possible with its behaviour and syntax, add recipe, make sure it works well with `notifiers`.

- A scenario or delivery can be exposed as a notify entity with `notify_entity`. Alert's `notifiers` are `notify` action names and not notify entities, so every notify entity also has a `notify` action of the same name.

## Delivery and Target Selection

### Inclusion Default

An advanced and very usable mode is to have all deliveries selected only explicitly/by scenario so nothing is notified unless asked for, rather than by
default everything. This works well to minimize noise. However it means every delivery has to have inclusion set to `scenario` or `explicit` manually - make an option in configflow UI to set a global default.

Sort out explicit/implicit/scenario. Two of these mean the same thing. There's a useful delivery mode which is effectively target driven - only consider the transport if there's a target that needs it. On other hand deliveries like Persistence that only make sense if explicit.

### Target-Driven Implicit Selection

A significant step landed here, but the item stays open - see "What's left" below.

Previously, whether a delivery was an implicit selection candidate (`select_deliveries()`) was decided purely by its transport's static `inclusion: default` flag, independent of what target was actually given in the call - `email`/`mobile_push`/`notify_entity`/`html5`/`alexa_devices` happened to be `default`, so a bare email address or a `notify.*` entity in `target:` "just worked" without naming a delivery, while a fully-qualified `target: {discord_channel: "x"}` went nowhere unless the call *also* named `discord` explicitly. The value didn't error - it just sat unclaimed, visible only via `unassigned_targets` in the archive.

Selection is now driven off three explicit category lists a transport declares on itself (`Transport.unique_target_categories`/`fallback_target_categories`/`other_target_categories`, `transport.py`): `unique` for a category shape/prefix or entity domain+platform nothing else could claim (`ATTR_EMAIL`, `discord_channel`, an html5-platform `notify.*` entity, ...), `fallback` for a category this transport only claims once nothing more specific did (`notify_entity`'s bare `notify.*` catch-all, after html5/alexa_devices' platform-scoped matches get first refusal), and `other` for categories a transport understands well enough to build a full envelope from but that are too ambiguous to drive auto-selection on their own (the `media_player` domain shared by kodi/tts/the `media` transport/alexa_media_player/chime). `Transport.inclusion_mode` is gone entirely - a transport's own base `inclusion` is now inferred from whether it declares any `unique`/`fallback` category at all (`default_inclusion()`, `transport.py`): `default` if it does, `explicit` if it doesn't, since a transport that can never definitively claim anything has no way to prove a given notification is relevant to it. `Notification.select_deliveries()` builds a per-notification "match pool" (the given target, each candidate delivery's own configured target, and each enabled recipient's own capabilities) and only actually enables a `default`-inclusion delivery once its transport's `unique`/`fallback` categories are found present in that pool (`_category_satisfied()`) - a cheap presence check, not full resolution. A delivery whose own config explicitly declares `inclusion: default` (`Delivery.explicit_inclusion`) is exempt from that check, so a fixed-target delivery with nothing in the call to match against (a permanent archive/BCC email, an mqtt delivery with a topic baked into its own `data:`) still fires as a deliberate, explicit choice - this is the "circular dependency" carve-out this section used to flag as unsolved.

This resolves the concrete bugs that motivated it: `discord`/`matrix`/`mqtt`/`telegram` now auto-select correctly off their own dedicated category (`discord_channel`/`matrix_room`/`topic`/`telegram_chat_id`), `notify_entity`'s "catch whatever html5/alexa_devices didn't" behaviour is now a real `fallback_target_categories` declaration instead of an informal `selection_rank` convention, and `kodi`/`tts`/the `media` transport/`alexa_media_player`/`chime` simply never auto-select (their shared `media_player`/entity domains are `other_target_categories` only) without needing a special case each. `OPTION_UNIQUE_TARGETS` (the old opt-in cross-delivery dedup) is gone - a fallback-category delivery now always excludes whatever an earlier-processed delivery already claimed (`Notification._is_fallback_only()`), unconditionally, since two different deliveries of the *same* transport competing for the same fallback-caught value was the only case it ever needed to guard against; two deliveries of a *unique*-category transport are never deduped, since a unique category already proves no other transport could have claimed the same value.

**What's left**: selection is still a cheap, approximate presence check, not full resolution - snooze filtering, `target_select` regexes and indirect (person/area/floor) resolution can still legitimately leave an implicitly-selected delivery with nothing to send, the same as before. `Notification._target_required()` (and the `implicit_only_deliveries` tracking, and the `missed`/`skipped` split both lean on) stays for exactly that residual gap - it's much less load-bearing now that most implicit selections have a real match by construction, but removing it would reopen the original noisy-warning failure mode on whatever slice of cases the cheap check still gets wrong. Closing that gap for good needs a bigger pipeline change - selection and target resolution genuinely unified into one pass - which is out of scope here.

Chime has a related problem one level down: it currently matches `switch`/`media_player`/`siren`/`script`/`rest_command` entities directly, borrowing other domains' shapes, rather than through its own named chime aliases. A further step is to make chime aliases into targets in their own right, so a chime delivery can be matched unambiguously by alias name instead.

Consider also typed dict, or classes, for the deliveries mapping carried around inside Notification so easier to verify by type the interactions across functions.

### Delivery Sequence

Might be scope for having 'real time' deliveries sequenced ahead of async ones, albeit email is as fast as mobile push for people and notifies similarly, and delivery times only really impacted by camera snapshots (although lacking metrics for some of the more obscure integrations).

## Setup and Configuration

### Extended UI Configuration

Second and further phases identified at [ConfigFlow](./rfcs/0001-configflow_approach.md)

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

Companion HACS components, with working term [Auto Notifier](./rfcs/0003-auto_notifier.md), starting with an [MVP](./rfcs/0003-auto_notifier.md#mvp) and sometime later a [Frigate Auto Notifier](./rfcs/0006-frigate_auto_notifier.md).
The Supernotify changes needed first are in [Auto Notifier Support](./rfcs/0003a-auto_notifier_support.md) though expected to be refined after the MVP.

### UI

There must be a better way of sharing dashboards than manual copy and paste of YAML from the [dashboard recipe](../recipes/notification_dashboard.md)

SignalK has nice idea of having recommended plugins, could be feature PR for HACS

### Extensibility

- Other developers able to create add-ons, see also [Auto Notifier](./rfcs/0001-auto_notifier.md)
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
  allowed by the `hacs.json` minimum of 2026.4.0, the tools just don't appear. Pin down the release and
  say so in the docs.
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

Entire missed deliveries are tracked but not missed targets. Most transports are fire and forget so don't know a target has failed - mobile_push is one that does if the `action` has gone away, and it is an important transport. This would include tracking in the logs and archived notification a list of failed targets, with reasons, and also flagging the entire delivery as 'partial' if an explicitly requested mobile_app couldn't be reached ( notification would be a `success` if multiple implicit targets generated and 1 of them failed)

Scenarios can mess with targets but its complicated in config and in code, and not clear how you could use a scenario to a) add targets, b) suppress targets, c) set a fixed list of targets. Presently requires delivery level target add.

## Completed Roadmap

- [ConfigFlow](./rfcs/0001-configflow_approach.md)
   - v2.0.0
   - Partially completed, basic YAML only
- [Deliveries and Transports](./rfcs/0002-deliveries_and_transports.md)
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
