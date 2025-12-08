# Public releases

## 1.5.0
### Features
- Mobile discovery now on by default
  - Use `mobile_discovery: false` for each recipient to switch off
- New Recipient discovery, on by default, based on Home Assistant's `person` entities
  - Use `recipient_discovery: false` in configuration to switch off
  - Use `enabled: false` to switch off specific people from automatic notifications
- Mobile Discovery can be switched off at platform or recipient level
- Recipient now exposed as an entity
  - Recipient can be enabled or disabled in Home Assistant UI, Automations, API etc by changing entity state
- Mobile Push delivery now configured by default
- `png_opts` now available for images, pre-set for email to `optimize: true`
- Camera snapshot now fixes/optimizes images like URL snapshot and Image Entity already do
- Media now has a `reprocess` option to switch off image rewriting, or preserve original metadata, incl comments
- Automatic housekeeping to purge images from `media_dir`
### Changes
- `enqure_people` is now `enquire_recipients` for consistency
### Internal
- Dicts for person and delivery customization now replaced by typed classes for type safety and easier refactoring / testing
- Refactored out common image handling code for all 3 grab methods

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
- `action` for mobile app notifications is now `mobile_app_id` to be clearer and avoid ambiguity with mobile push actions
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
