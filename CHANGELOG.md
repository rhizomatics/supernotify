# Public releases

## 1.8.0
### TTS Transport
- New transport for TTS integration, hiding its complicated double entity_id call
### Generic Transport
- New `raw` option to switch off domain-specific shaping of `data` contents
- Will now prune fields for `tts`
### HTML Email Templates
- `alert` template object now preserved in `debug_trace` for archived notifications
- `alert.server.language` added for Home Assistant configured language code, e.g. `en`
- `alert.preheader` added for pre-header text, defaulting to combination of title and message
- Added new `strict_template` to the transport option to perform more validation of template, useful when developing new templates
- Changed Alert variables to TypedDicts
- Added `ensure_valid` step before rendering
- Switched off `parse_results` for rendering
- Fixed Jinja2 format and variable name issues in default template
- `action_url` and `action_url_title` now passed to template
- Corrected `snapshot_url` to be taken from `media` section as other transports
### Media Player Transport
- Corrected `snapshot_url` to be taken from `media` section as other transports
## 1.7.0
### New
#### Scenario
- Scenarios can now use regular expressions for the delivery configuration, for example `.*` to apply to all
- `enquire_deliveries_by_scenario` action now lists which deliveries are enabled by the scenario, disabled by it, and all the scenarios to which it applies overrides
- `delivery` section now has the same flexibility as on an action call - it can be a mapping, list or single string, the latter two are all that is needed to simply enable deliveries
#### Cameras
- Camera entity's built in device tracker will now be used, no need for separate device tracker where this supported
- Better diagnostics for unavailable cameras
### People / Recipients
- Automatically discovered mobile devices merge into manually registered ones rather than overwriting them
- Enabled flag for deliveries in Recipient are now respected in delivery selection
  - Recipient overrides can now re-enable otherwise disabled deliveries, as scenarios have already been able to do
  - Like scenario, deliveries can be overridden without enabling by setting `enabled:` as empty value
  - `recipient_enable_deliveries` recorded in `debug_trace` as in the notification archive
#### Notification Archive
- Further improvements to `Notification` archive object to make it easier to debug
    - Original message now at top of object
    - Envelopes for each delivery categorized into `delivered`,`failed`,`skipped` and `no_envelopes`
    - More stats on notification outcomes
#### Email Templates
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
### Features
- Chime alias error handling improved
  - Humanize validation errors
  - Validate targets and build Target objects at start-up
  - Normalize and default the alias config at start-up
  - Chime alias can now have an empty config - where the alias is the tune and domain needs nothing else
  - scripts now run async with `script.turn_on`, with `wait: True` if delivery debug flag on
- Media Player
  - Data section now uses the modern HA style with `media:` subsection rather than old Alexa Media Player style, which works with new style
### Internal
- More logging for device inclusion/exclusion during discovery
- Defaulting for device inclusion/exclusion from hard-coded values switched off by either explicit include or exclude ( affects Chime use of `Speaker Group` as default exclusion)
- Easier to check archived notifications
  - Both `delivered_envelopes` and `undelivered_envelopes` list envelopes by transport rather than a flat list
- Centralize results handling for notification
- Test Context can now take yaml rather than just dicts for config snippets
- Chime now has MiniChimeTransport to replace the if logic and dicts for chime transports
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
