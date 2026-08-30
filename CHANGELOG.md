

## 2.2.0

* Recipients
  * Recipients are now **Notify Entities**, so can be called with `send_message` directly from automations, and also support being member of a **Notify Entity Group**
  * Undocumented `recipients` key on notify action data now deprecated, specify recipients as regular targets
  * Improved handling of Recipients specific disablement of deliveries
* Cameras
  * `ptz_method` now defaults to `frigate` if the camera defined by the frigate integration even if no `camera` definition provided in config
  * `ptz_delay` defaults to `10` if not defined in camera config, or camera not defined at all

## 2.1.0

Gratitude to [@lollox80](https://github.com/lollox80) for contributing 4 new transport integrations

### Matrix transport

- New native `matrix` transport using `matrix.send_message`: html/text format, threads, camera snapshot attachment, optional priority emoji prefix, room target validation. See `docs/transports/matrix.md`.

### Kodi transport

- New native `kodi` transport: on-screen overlay notifications via `kodi.call_method` / `GUI.ShowNotification` on any `media_player.kodi_*` entity, priority-mapped icon, camera snapshot as overlay icon. See `docs/transports/kodi.md`.

### Discord transport

- New native `discord` transport: markdown title, rich embeds, camera snapshot upload, remote image URLs, optional priority emoji prefix, 2000-char truncation. See `docs/transports/discord.md`.

### HTML5 transport

- New native `html5` browser push transport using the modern `html5.send_message` entity service: priority-mapped urgency, tag/renotify, action buttons, snapshot image URL, `silent`/`vibrate` exclusivity guard. See `docs/transports/html5.md`.

## 2.0.0

### ConfigFlow

- SuperNotify is now set up using the standard HomeAssistant UI ('ConfigFlow')
  - This covers basic use cases using default deliveries, like mobile push and email
  - More advanced configuration - like scenarios, cameras, transport, action configs etc - continues to require YAML configuration
  - That YAML now lives under a top-level `supernotify:` key, not the old `notify: - platform: supernotify` block - typically split out with `supernotify: !include supernotify.yaml`
  - The config entry is now the sole, unconditional owner of the `notify.supernotify` action - no more dual registration between YAML and the UI
  - A leftover `notify: - platform: supernotify` block is inert (nothing is registered from it) but raises a fixable repair that automates the move: writes `supernotify.yaml`, adds the include line, reloads immediately - no restart needed. Migrating by hand instead works just as well; either way, deleting the old block afterwards is what makes the repair stop reappearing
  - A custom `name:` from that old block (which determines the actual `notify.<name>` action, e.g. `name: SuperNotifier` → `notify.supernotifier`) is kept in sync automatically on every load, independent of whether the repair has been run yet - existing installs don't lose their action name mid-upgrade
  - Core config (archive/dupe_check/housekeeping/paths/name) is reconfigurable via UI, and now actually applies immediately via an update listener - no reload/restart needed

### SMTP

- v1.17.0 introduced a separate `smtp` transport to work round problems created by new Home Assistant Notify Entities. To make this less confusing, the new direct SMTP integration is merged back into the `email` transport, switched on by a options keyword
- Existing deliveries will have a warning in the logs, and will attempt to redirect to the `email` integration in direct mode, although in practice changes will be required to config to remove the `smtp` transport references (which has only been available for 1 week)

### Technical Changes

- Step 1 of the [roadmap](docs/roadmap/configflow_approach.md) updated to minimize reuse of 'legacy' integration style, then extended further to retire that legacy style entirely for the notify-platform registration
- Details
  - `config_flow.py` — zero-required-field user step (reproduces `minimal.yaml`), options flow with archive/dupe_check/housekeeping pages, single_config_entry enforced, plus a `name` field determining the registered action.
  - `__init__.py` — CONFIG_SCHEMA/async_setup for the top-level `supernotify:` key; `async_setup_entry` unconditionally owns `notify.supernotify`, computing the service name from `entry.data[name]`; an update listener reloads the entry so options/reconfigure changes apply immediately.
  - `notify.py` — `async_get_service` (the legacy `notify:` platform entrypoint) reduced to a shim: raises the migration repair and syncs `entry.data[name]` from the legacy config on every load, but registers nothing itself.
  - `manifest.json` — `config_flow: true`, `single_config_entry: true`, notify added to dependencies.
  - `strings.json` + all 11 translations/*.json — new fields, options pages, and the migration repair's fixable flow text.
  - `schema.py` — split into `SUPERNOTIFY_YAML_SCHEMA` (8 YAML-only keys), `CONFIG_ENTRY_SCHEMA` (8 ConfigEntry-owned keys), `FULL_CONFIG_SCHEMA` (single-pass union, for tests) - `_entry_full_config` validates entry.data/options through `CONFIG_ENTRY_SCHEMA` and merges in the already-validated YAML section as-is, rather than re-validating a combined dict a second time (which would reject values a first pass already coerced, e.g. `cv.template`'s `Template` objects).
  - `repairs.py` (new) — the `legacy_yaml_config` fixable repair: writes `supernotify.yaml` + appends the include line, validated on the event loop before writing (`cv.template`'s bare-Jinja-string condition shorthand needs the event-loop-bound `hass` context, so this can't happen from the executor thread the file I/O runs in), validates configuration.yaml as a whole before and after via `async_check_ha_config_file`, rolls back and logs the underlying error on any failure, raises a separate persistent `legacy_yaml_manual_migration_required` issue when automation can't proceed, and serializes the whole write-and-reload sequence behind a lock so two concurrent attempts can't interleave.
  - Tests: `test_config_flow.py`, `test_init.py`, `test_repairs.py` (new), `test_config_yaml.py`, `test_example_configs.py` all updated/added for the new architecture.
  - Docs: `docs/configuration/yaml.md`, `email.md` and `docs/recipes/contextual_mobile_actions.md` updated for the top-level `supernotify:` key; `docgen/schema_extractor.py` updated for the renamed schema.
  - Fix log errors from accessing version in `manifest.json` and eager loading MQTT component
- Silver level HA Quality Level Checks
  - Stage 2 of the roadmap partially implemented, 'Bronze' level only
  - Better testing of user supplied values in config
  - Additional services moved to shared yaml/ui config code
  - Improved exception handling
- Template Path
  - Directory now created if specified and doesn't exist
  - Default is relative to config home rather than hard-coded to `/config`
  - Better logging for path actions
- Async I/O
  - Final 2 `media_grab.py` Pillow image I/O wrapped as async
  - SMTP attach file now uses `aiofiles`

## 1.17.1
- New standalone `smtp` integration will reuse connection details from an existing Home Assistant SMTP integration
  - Only for the new UI based SMTP configuration, not the original yaml configuration
  - This can be used to avoid defining the same information twice

## 1.17.0
- Adds an alternative `smtp` integration which preserves the original Home Assistant behaviour
  - No need to have the overhead of pre-registering every e-mail address as a 'notify entity'
  - Attachment, template and HTML behaviour identical to existing email integration
  - Emails using `smtp` support `Importance`,`Priority`,`X-Priority` and `X-MSMail-Priority` headers. Values are mapped automatically from the Supernotify priority.
  - `Message-Id` in email header ties back to notification ID and delivery name
  - `default_title` option for emails without titles set in notification
- `delivery_selection` of `fixed` overrides priority and condition filtering at delivery level, if selection is fixed, only `enabled` at transport or delivery level will override your command.

## 1.16.6
- Upgrade dependencies and tests for HA 2026.8.0
- Support for changes to Device Manager in HA 2026.8 and later
 - Details at https://developers.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry
 - Fallback to previous behaviour for older versions of Home Assistant that don't have the new device API for config entries
 - Quality Scale re-audited
 - Roadmap added for migration to ConfigFlow and improved HA quality scale level
 - Removal and clean up instructions added to 'Getting Started' guide
## 1.16.5
- Fix wildcard scenarios selecting other scenarios that wouldn't otherwise be matched
- Test fixes by pinning `pytest-homeassistant-custom-component`

## 1.16.4
- Upgraded to Ruff 0.16.0 and enabled full rule set, fixed resulting lint errors
- Added `EnvelopeOutcome` enum to replace previous `KEY_` constants
- Archived notification now has a single `outcome` value for overall delivery result
- Archived notifications have separate `delivery_exceptions` field for transport errors
## 1.16.3
- Dependencies update, incl HA compatibility linked to 2026.7.x ( maintaining 2026.2.x for py3.13 testing )
- Test fixes for recent HA changes
## 1.16.2
- Dependencies update, incl HA compatibility linked to 2026.6.x ( maintaining 2026.2.x for py3.13 testing )
## 1.16.1
### Mobile Push
- Device selection (by model,manufacturer etc) now applies at delivery time not just discovery time, so the global discovery by person doesn't have to be switch off to create a phone model specific delivery
### Chime
- Device selection (by model,manufacturer etc) now applies at delivery time not just discovery time
### TTS
- Device selection (by model,manufacturer etc) now applies at delivery time not just discovery time
## 1.16.0
### Mobile Push
- Data sections can now be filtered in/out to any level of nesting
  - Common use case - trimming out values from Frigate blueprint like `attachment` or `video` that can result in broken thumbnails for Apple notifications
  - [Fix Frigate Apple Push](recipes/fix_frigate_apple_push.md) reciped added.
## Generic
- The nested support for `data` filtering introduced for Mobile Push introduced also for Generic transport
## Other
- Version of Supernotify added to archived notification
## 1.15.0
### New transports
- Pushover, Telegram and LaMetric, contributed by [@lollox80](https://github.com/lollox80)
### Multimedia
- New `media_url_prefix` in platform settings to control the URL path which Home Assistant uses to expose the media directory. Make this empty to stop the directory being available via HA web UI
- Fix media cleanup job handling of files in subdirectories
- Removed absolute URL transform for mobile push, so companion app can resolve with appropriate URL
### Mobile Push
- By default, thumbnail image is captured at time of notification
- Better Android integration
- Multiple new tuning keys for `data` section to use Android or iOS features
- Where they can be positively identified, iOS and Android devices are only sent `data` fields they support
## 1.14.1
### PTZ
- Mobile Push deliveries will defer until a PTZ operation complete
## 1.14.0
### Delivery Sequencing
- Delivieries now use asyncio.gather to maximize parallelism
- Deliveries needing snapshot images sequence after simple service calls
- Camera PTZ call initiated at the start, so motion can complete in background while service calls happening
### New Transports
- [Gotify](https://gotify.net) contributed by [@lollox80](https://github.com/lollox80)
- [Ntfy]() is now its own transport, (with older mechanism still available in Generic Transport), contributed by [@lollox80](https://github.com/lollox80)
### Bug fixes
- Multiple bug fixes contributed by [@lollox80](https://github.com/lollox80)
- GitHub actions now runs tests and lints for both py3.13 and py3.14
### Diagnostics
- Call record now has a timestamp for service call
## 1.13.0
### Transport Generic
- Replaced hard-coded allow-list of fields per underlying service with dynamic validation using the service's action schema to prune out unsupported fields or make type conversions.
  - Generic can also now support a much wider set of Home Assistant built-in and custom integrations reliably, pruning out data wherever a schema is provided
- Added support for [notify_events](https://www.home-assistant.io/integrations/notify_events), translating standard priority and passing on image URLs in expected format. Use `handle_as_domain: notify_events` on Delivery options for the specific processing
- Corrected `ntfy` integration handling of images and actions
### Archiving
- Use local timezone for archive notification file path
## 1.12.2
- Prioritize data from action call over scenario or target derived data
- Minor test and lint fixes for 3.14, and improved test coverage
## 1.12.1
- Translations for Dutch, French, German, Hindi, Italian, Japanese, Polish, Portuguese, Simplified Chinese and Spanish
- Vertalingen voor Nederlands, Traductions en français, Übersetzungen auf Deutsch, हिंदी में अनुवाद, Traduzioni in italiano, 日本語の翻訳, Tłumaczenia po polsku, Traduções em português, 简体中文翻译 en traducciones al español
## 1.12.0
### Alexa Media Player
Includes major fixes and improvements contributed by [@lollox80](https://github.com/lollox80)
- Alexa Media Player volume control now works, along with ability to pause and restart any music previously playing
- `spoken_message` can now be set in `data` as an alternative to `message` for any of the voice options (TTS, Alexa Media Player, Alexa Devices)
### Delivery Overrides
- Overrides now respect `message` or `title` in the `data` section for channel specific messages
  - New [recipe](recipes/channel_specific_messages.md) to illustrate it
- Overrides now match against the name of a transport if there's no matching delivery
- Delivery overrides that have indirect targets like `person` now correctly resolved to email / sms / slack / mobile etc
- Explicitly enabled deliveries in action call not overridden by scenarios

## 1.11.1
Includes fixes and improvements contributed by [@lollox80](https://github.com/lollox80)
-  Icon fixes
- `notification_id` suppressed in persistent notification if null
- Archive file names sanitized for Windows/SMB
- URLs in action groups allow `homeassistant://` deep links
- Suppress repeating `condition_variables` from archived envelopes
- Expand templated values in `data` for archiving
- Migrate old `condition` to `conditions`
## 1.11.0
### Dupe Checking
- `force_resend` can be set in `data` section to override dupe handling ( contribution by [@lollox80](https://github.com/lollox80))
- `dupe_policy_message_title_same` duplicate detection policy added
### Internal
- Added more tests, focusing on transports and media_grab
## 1.10.1
- Lint and type fixes
## 1.10.0
Includes Italian translations, fixes and improvements contributed by [@lollox80](https://github.com/lollox80)
### Configuration
- New `snooze` config, with configurable default snooze time to replace hard coded 1 hour
### Templating
- Extra data passed via notification now available on templates as `notification_data`
### Archive
- Can now send HomeAssistant events in the archiver, which also
enables Syslog or OTLP event creation using [Remote Logger](https://remote-logger.rhizomatics.org.uk)
- `debug` option replaced by `diagnostics` to automatically switch maximal archive messages on or off
depending on notification outcome, using same policy as event selection
### Fixes
- Deprecated and obsoleted icons replaced
- Sanitizing messages for voice assistants now strips emojis and other weird unicode
- Archive writing now async
- Corrected MDI icons for developer tools view
## 1.9.4
### Internal
- `__init__.py` refactored into `schema.py` and `const.py`
- Python default now 3.14, in line with Home Assistant
- Added translations for Italian, French, German and Spanish
- Primary target Home Assistant version now 2026.3
## 1.9.3
### Dependencies
- Primary target Home Assistant version now 2026.1
### Scenario names
- Added `NO_SCENARIO` as a reserved name for scenarios, since Home Assistant Dev Tools action panel will translate `NULL` into
a None value
- Scenario names now validated at startup
### Action Data Validation
- Improved handling of failures in humanize library to handle validation
## 1.9.2
### Fixes
- `snapshot_image_path` now always a string rather than path object when added back to `data`
- Prevent a dict or list value for `priority` raising unexpected error
## 1.9.1
### Cameras
- Allow a separate entity id for PTZ movements, `ptz_camera`
## 1.9.0
### Device Discovery
- Now configured via `options` and can be used for mobile_app_ids or device_ids
- Mobile app discovery improved, no longer needs mobile app device trackers to be configured in Home Assistant Person screen
- Discovery now happens at *Delivery* level rather than *Transport*
  - Discovery can filter in or out device by platform, operating system, area_id, label, model or manufacturer
- Mobile App info now has a typed class rather than dict for better type safety
- More attributes now picked up for mobile app, incl OS name and version, app version, user_id, area_id and label
- Discovered mobile apps are linked back to people, and recipient objects, where possible
- Allow auto-discovered mobile apps to be disabled for notification in Recipient
- Device discovery now also occurs for auto generated default delivery, e.g. mobile_push
### Mobile Push
- Now supports push to all known mobile apps using device discovery, not just the Device Trackers assigned in the Person integration
### TTS
- TTS Transport Adaptor supports TTS delivery to Android mobile apps
### Delivery Options
- All `include` options now consistently use the selection block model and named in `xxxx_select` pattern
   - Also means that target selection now supports inclusion or exclusion
   - Auto upgrade of previous deprecated options, though only live, config now re-written
### Deprecated
All deprecations will be automatically handled in config as if newer config used, and details sent to log
#### Options
- `data_keys_include_re` - Use `data_keys_select`
- `data_keys_exclude_re`  - Use `data_keys_select`
- `target_include_re` - Use `target_select`
#### Transports
- `device_discovery` - Use `device_discovery` in `options:`
- `device_options` - Use `device_options` in `options:`
- `device_model_include` - Use `device_model_select` in `options:`
- `device_model_exclude` - Use `device_model_select` in `options:`

## 1.8.2
### Debugging
- Debug trace now holds exception traces for email templates and chime action building
- Transport Adaptor entities now expose more transport specific attributes
### Email Transport
- Extra check on template living on file system
### Example HTML Email Template
- Now the default template always available, though overridable
- Colours now set by priority, `message_html` used if set, and general cleanup
- Example renders now on docs page
## 1.8.1
### Generic Transport
- Can now adapt a message for the *ntfy* Home Assistant integration
- Entity selection is now specific to the domain, e.g. `switch`,`input_text`,`notify`
### Priority
- Custom priorities now supported ( default continues to be `medium` )
- New standard priority `minimum` and mapping of all priorities to the common `1..5` range with 5 as `critical`
## 1.8.0
### TTS Transport
- New transport for TTS integration, hiding its complicated double entity_id call
### Generic Transport
- New `raw` option to switch off domain-specific shaping of `data` contents
- Will now prune fields for `tts`
### Email Transport
- The first available `smtp` integration is automatically configured as `DEFAULT_email` delivery
  - So, zero-config usage now accepts notifications with email addresses as targets
### HTML Email Templates
- `alert` template object now preserved in `debug_trace` for archived notifications
- `alert.server.language` added for Home Assistant configured language code, e.g. `en`
- `alert.preheader` added for pre-header text, defaulting to combination of title and message
- New options `preheader_blank` and `preheader_length` to control packing out the pre-header with blanks for cleaner inbox visibility
- Added new `strict_template` to the transport option to perform more validation of template, useful when developing new templates
- Changed Alert variables to TypedDicts
- Added `ensure_valid` step before rendering
- Switched off `parse_results` for rendering
- Image now available for attachments, previously only where `snapshot_url` given
- Fixed Jinja2 format and variable name issues in default template
- `action_url` and `action_url_title` now passed to template
- Corrected `snapshot_url` to be taken from `media` section as other transports
### Media Player Transport
- Corrected `snapshot_url` to be taken from `media` section as other transports

## 1.7.0
### Scenario
- Scenarios can now use regular expressions for the delivery configuration, for example `.*` to apply to all
- `enquire_deliveries_by_scenario` action now lists which deliveries are enabled by the scenario, disabled by it, and all the scenarios to which it applies overrides
- `delivery` section now has the same flexibility as on an action call - it can be a mapping, list or single string, the latter two are all that is needed to simply enable deliveries
### Cameras
- Camera entity's built in device tracker will now be used, no need for separate device tracker where this supported
- Better diagnostics for unavailable cameras
### People / Recipients
- Automatically discovered mobile devices merge into manually registered ones rather than overwriting them
- Enabled flag for deliveries in Recipient are now respected in delivery selection
  - Recipient overrides can now re-enable otherwise disabled deliveries, as scenarios have already been able to do
  - Like scenario, deliveries can be overridden without enabling by setting `enabled:` as empty value
  - `recipient_enable_deliveries` recorded in `debug_trace` as in the notification archive
### Notification Archive
- Further improvements to `Notification` archive object to make it easier to debug
    - Original message now at top of object
    - Envelopes for each delivery categorized into `delivered`,`failed`,`skipped` and `no_envelopes`
    - More stats on notification outcomes
### Email Templates
- Loading templates and rendering now using non-blocking IO
- Standard Home Assistant templates used for full range of variables and filters


## 1.6.0
### Fixes
- Image attachments from mobile push style notifications not being picked up by e-mail
   - This affected use of the Frigate Blueprint to generate both e-mail and mobile push with image attachment
   - E2E Recipe test now in place for Frigate Blueprint notification to prevent regression
### Changes
- Better Home Assistant standards compliance
  - Exposed entities are now correctly named in the `binary_sensor` platform rather than inventing a new one
  - Replaced `ValueError` with `ServiceValidationError` and `HomeAssistantError` for HA compatibility
- Configuration technical entity now replaced with a `enquire_configuration` service
- Easier to debug failed deliveries
    - Archived notification now has a `deliveries` dict
    - It has all delivered and un-delivered envelopes, plus details of deliveries that had no envelopes generated.
    - Can see in one place now what happened with each selected delivery
### Internal
- Excess kwargs for `Context` now logged correctly
- HomeAssistant access from `notify.py` now consistently via `hass_api`
- Added turbojpeg dependency to allow `mobile_app` integration to be setup for non-mocked testing
- Notification
  - Moved `snapshot_image_path` for Notification inside `media`
  - Moved `delivery_errors` into the new `deliveries` structure under `errors`
  - Cleaned up unused `delivery_results`
- Generic Transport
  - Removed the default `entity_id` filter for `target_categories` option
  - Fixed the provision of targets where no `target_categories` defined - all targets supplied in one big list
- Added Home Assistant quality score report and config file
  - Replaced blocking PIL image operation and BS4 html parsing with wrapped async executor
  - All http get now consistently used a HomeAssistant provided aiohttp session
  - Set PARALLEL_UPDATE to 0 since no operations outside of existing HomeAssistant services
  - Technical states are now actual entities, marked as TECHNICAL category and with icons
  - `iot_class` now `calculated` for better HA consistency
  - Moved tests to `tests.components.supernotify`
  - Removed lots of pointless checks on HA presence in `hass_api`
- Recipient
  - Removed shadow state, now goes straight to Person
## 1.5.3
### Chime Transport
- Chime alias error handling improved
  - Humanize validation errors
  - Validate targets and build Target objects at start-up
  - Normalize and default the alias config at start-up
  - Chime alias can now have an empty config - where the alias is the tune and domain needs nothing else
  - scripts now run async with `script.turn_on`, with `wait: True` if delivery debug flag on
  - Chime now has MiniChimeTransport to replace the if logic and dicts for chime transports
  - Defaulting for device inclusion/exclusion from hard-coded values (`DEVICE_MODEL_EXCLUDE`) switched off by either explicit include or exclude ( affects Chime use of `Speaker Group` as default exclusion)
### Media Player Transport
  - Data section now uses the modern HA style with `media:` subsection rather than old Alexa Media Player style, which works with new style
### Archived Notification
- Easier to check archived notifications
  - Both `delivered_envelopes` and `undelivered_envelopes` list envelopes by transport rather than a flat list
- Centralize results handling for notification
### Internal
- More logging for device inclusion/exclusion during discovery
- Test Context can now take yaml rather than just dicts for config snippets

## 1.5.2
### Fixes
- Better error handling for broken scenario conditions
## 1.5.1
### Features
- Generic Transport
   - Now has direct support for `input_text.set_value`,`script`,`rest_command`,`light`,`siren`,`mqtt` and `switch`
      -  Will build a `data` and `target` to meet the rules of the automations, pruning out fields that would break the call
   - New delivery options `data_keys_include_re` and `data_keys_exclude_re` to control valid keys in `data` section
   - New delivery option `handle_as_domain` to structure an action that Generic transport adaptor
   doesn't know about in the same way as one that it does, like `input_text` or `light`.
- Debugging
  - Undelivered envelopes now have a `skip_reason` of `NO_ACTION` or `NO_TARGET` if action call
to Home Assistant skipped because of mandatory missing items

## 1.5.0
### Features
- Mobile Push
    - Mobile discovery now on by default
        - Use `mobile_discovery: false` for each recipient to switch off
    - New Recipient discovery, on by default, based on Home Assistant's `person` entities
        - Use `recipient_discovery: false` in configuration to switch off
        - Use `enabled: false` to switch off specific people from automatic notifications
    - Mobile Discovery can be switched off at platform or recipient level
    - Recipient now exposed as an entity
        - Recipient can be enabled or disabled in Home Assistant UI, Automations, API etc by changing entity state
    - Mobile Push delivery now configured by default
- Multimedia
    - `png_opts` now available for images, pre-set for email to `optimize: true`
    - Camera snapshot now fixes/optimizes images like URL snapshot and Image Entity already do
    - Media now has a `reprocess` option to switch off image rewriting, or preserve original metadata, incl comments
    - Automatic housekeeping to purge images from `media_dir`, configurable by `media_storage_days` in `housekeeping`
    - `purge_media` service to run the media storage housekeeping on demand
- Chime
    - Chime Aliases configuration now validated at start up, and schema published
    - Device Discovery can now include or exclude by device model
        - Chime integration uses this so doesn't select Alexa actual devices and Alexa Group devices
    - Added `rest_command` to supported transport methods
- Scenarios
    - Scenario overriding improved for `data` and `target`
    - Scenarios can now disable deliveries
    - `enabled` can now be left null for Scenario delivery config, to apply only where delivery already selected
        - The seasonal scenario recipe demonstrates this
- Duplicate Suppression
    - Dupe checking now happens at Envelope rather than Notification level, so same message can go out to different deliveries and/or recipients
### Changes
- `enqure_people` is now `enquire_recipients` for consistency
### Internal
- Dicts for person and delivery customization now replaced by typed classes for type safety and easier refactoring / testing
- Refactored out common image handling code for all 3 grab methods
- Notification slimmed down and focussed, message and title handling moved to Envelope, Notification will
only prepare data and targets
- Dupe checking code moved out of Notify to its own class
- `delivery_by_scenario` pre-compute and refresh removed
- Moved code to detect media requirements in mobile actions out of Notification and into the mobile_push transport
- Test suite for the seasonal scenarios
- Correct debug handling for archival, and inclusion of debug_trace

## 1.4.0
### Features
- Now supports the full `conditions` Home Assistant schema, `condition` is now deprecated though still supported
  - This allows simple lists of shortcut templates, for common `AND` type usage
### Internal
- Test config now consistently applies schema validation/enhancement
## 1.3.5
### Fixes
- Condition variables could be rejected in validation of Delivery conditions
### Internal
- More extensive condition testing, condition variables now always applied
## 1.3.4
### Features
- Improved documentation content and navigation
- Media Player transport allows `media_content_type` to be overridden in `data` for non-image use
- Archiving now has a `debug` option, which controls if `debug_trace` included in notifications
- Alexa Devices transport now has unique recipients on by default ( so if accidentally an Alex 'speak' delivery and
an Alexa 'announce' delivery is selected, only one of them will speak for each device)
- Transport adaptors now count errors and report last error time and type
### Internal
- Renaming of transport tests for consistency with package names
- Updating `media_player`,`title_handling` and `chime_aliases` references for consistency
- `archive` module refactored into an `ArchiveDirectory` with all file system logic
- New envelope specific tests
- Improved tests by using deeper dummy/broken delivery which call through to HA API
## 1.3.3
### Features
- Added more direct documentation links for repairs
### Bug Fixes
- Corrected obsolete github pages docs link
## 1.3.2
### Features
- Exposed entities now use the alias as the 'friendly name', so shows up better in Developer Tools and entity view
- Add debug mode for deliveries, configurable at `transport` or `delivery` level
  - Response from service stored in `CallRecord` in the envelope and available in the archived notifications
  - In debug mode, service calls are synchronous rather than fire'n'forget so will fail immediately rather than in the background
- Home Assistant Actions (aka "services") that require a response be accepted are now supported
### Internal
- Transport tests re-organized and more added
- Transport now has an `override_enabled` for run time control of all deliveries using the transport via HA entities UI
- Bug fixes for null values in snoozer, and fix backward boolean compatibility for target_required

## 1.3.1
### Internal
- Update of 1.3.0 from beta 6 to beta 8

## 1.3.0
### Features
- *Notify Entity* transport now only selects unique targets, so if a Notify Entity has been delivered
in the same notification call, for example by *Alexa Devices*, it won't be called again for a duplicate
announcement. Closes issue[#8](https://github.com/rhizomatics/supernotify/issues/8)
- *Deliver* can now have a list of target inclusion regexes, useful for excluding Alexa `_speak` devices
or for custom notifications using *Generic* transport
- *Target* definition for *Delivery* or *Transport* can now be more flexible
  - Allows a structured dict, a single value, or list of strings.
  - Structure only required where category can't be inferred, so entity_ids, device_ids, email and phone numbers are fine
- *Deliver* has a new `target_usage` key, taking values of:
  - `no_action` only uses the Delivery target if there's no target on the notification action call
  - `no_delivery` only uses the Delivery target if there's no target applicable to this delivery
  - `merge_delivery` combines the targets in the Delivery with any on the action call, only where delivery already has a target
  - `merge_always` combines the targets in the Delivery with any on the action call, or if there's
  no target on the notification, it defaults to the Delivery target
  - `fixed` only ever delivers to the targets in the Delivery config, ignoring any direct or indirect (for example `person_id`) in the action call
- Entity states for Delivery and Transport now directly reflect configuration
- `target_required` is no longer boolean (although backward compatible), and now has values `always`,`never` and `optional`.
   - If set to `never` it speeds up delivery and debug traces by not computing targets when they're not needed
- Improved DebugTrace - more stages, shows `NO_CHANGE` when no effect
- Documentation improved - core concepts and principles, transports, more schema definitions
### Internal
- *Transport* implementations simplified, `select_targets` now replaced by options to select
target categories, for example `entity_id` and a list of inclusions regexs
- *Target* now has dunder method to support subtraction, for the targets only, and a `safe_copy` method
- *Notification* object now maintains a list of all the target values selected by deliveries, and this
is archived for debug purposes ( and supports the new unique target value functionality)
- *Snoozer* now uses `timedelta` rather than integer seconds to measure snooze length
- More tests for `common`

## 1.2.3
- `Delivery` now responsible to select targets, delegating to `Transport` where overridden
  - This means target category selection for generic deliveries is configured per delivery, e.g. telegram and discord
- `Target` overhauled to simplify repetitive logic, minimize getattr use, and allow custom domains
- Custom target domains now supported, so can have a `discord` target in addition to the standard `entity_id`,`email` etc
- `action` for mobile app notifications is now `mobile_action` to be clearer and avoid ambiguity with mobile push actions
- All personal target resolution now done at start up, and a `Target` object added to people registry entries
  - Easier to debug target selection now, and the email/sms/mobile_push transports are simpler

## 1.2.2
- Consolidated all transport defaults in a single method
- Simplified handling of transport and delivery config defaults
- Moved `target_required` from transport to delivery config, since could vary per delivery for generic transport
- Added `selection_rank` for delivery, and made *Notify Entity* transport resolve last
  - This is to support future resolution of [issue [#8](https://github.com/rhizomatics/supernotify/issues/8)]
- Notification now records a `missed` count, where transport runs without error but makes no deliveries
- `NotifyEntity` now always auto-generates a default Delivery unless the transport is explicitly disabled
- HomeAssistant target version now 2025.11

## 1.2.1
- HACS Hassfest validator added
- A delivery for `NotifyEntity` is now auto-generated for an empty platform config
  - If any deliveries are configured, then `NotifyEntity` must be included if needed, since won't be auto-generated
- The old unused 'default delivery by transport' removed
- `transport.transport` is now `transport.name`
- Simplified notification logic by passing new `Delivery` object and avoiding re-lookups
- Removed `default` for Delivery which had been replaced long ago by `selection` enum
- Removed `DEFAULT` scenario and replaced by *Implicit Deliveries* managed by `DeliveryRegistry`
- Added new `enquire_implicit_deliveries` Action
- Added more tests for `hass_api`

## 1.2.0
- `DeliveryRegistry` now has the delivery functionality from `Context` and `Transport`
- `DeliveryMethod` is now `Transport`
- Tests simplified with a new configurable `TestingContext`
- Moved mqtt, states, device, condition etc access into `HomeAssistantAPI` from across the code base
- `NotificationArchive` now owns its own Config interpretation and is built from notify
- Context is now a passive ref container plus a little FS path manipulation

## 1.1.6
- HomeAssistant logic moved from `Context` to `HomeAssistantAPI`
- Initialization logic moved from `Context` to `SupernotifyAction`
- References to `SupernotifyAction` now consistent rather than `SuperNotificationAction`
- Move camera PTZ and image handling from `Notification` to `media_grab.py`

## 1.1.5
- New tests for mqtt and notify entity handling and media grabbing
- ScenarioRegistry added to move scenario logic out of `Context`

## 1.1.4
- Explicit delivery selection in action overrides scenario disablement
- Extended and reorganized documentation
- Suppressed notifications now have a reason recorded, DUPE, SNOOZED, NO_SCENARIO

## 1.1.3
- Move out all people functionality from Context to new PeopleRegistry
- Move runtime model classes out of `__init__.py`
- Add new Target class that holds and filters recipients
- Simplify logic for generating recipients and envelopes
- Experimental new MQTTTransport

## 1.1.2

- Remove transport options where not relevant - chime, media_image

## 1.1.1

- Options defaulting for transports improved
- Archive checks for MQTT client first, and all file IO aio based

## 1.1.0

- Refactored internal use of dictionaries for delivery config, transport defaults and targets to typed classes for easier debugging and testing
- Dupe suppression now alphaizes hashes to avoid notification storms where a counter or timestamp defeats the dupe check
- Actions now separate out target data for service call wherever supported
- MQTT topic archive now works if file archive also switched on

## 1.0.4

- Test fixes, archive logging, and archive publish error handling
- Scenarios, transports and deliveries can be switched on or off via their exposed entities in Home Assistant UI or API
- `NotifyEntityTransport` added as pre-production

## 1.0.3

- Improve mqtt notification archiving by generating unique qualified topic per item
- Simplify archive config to be clear what applies to file and what to mqtt

## 1.0.2

- Validate mis-spelled variables in Scenario Condition templates and generate repairs

## 1.0.1

- Added repairs for configuration issues
- GitHub actions and pre-commit improvements

## 1.0.0

First public release of productionized home code
