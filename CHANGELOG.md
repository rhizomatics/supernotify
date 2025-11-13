# Public releases

## 1.3.0
- *Notify Entity* transport now only selects unique targets, so if a Notify Entity has been delivered
in the same notification call, for example by *Alexa Devices*, it won't be called again for a duplicate
announcement. Closes issue[#8](https://github.com/rhizomatics/supernotify/issues/8)
- *Deliver* can now have a list of target inclusion regexes, useful for excluding Alexa `_speak` devices
or for custom notifications using *Generic* transport
- *Transport* implementations simplified, `select_targets` now replaced by options to select
target categories, for example `entity_id` and a list of inclusions regexs
- *Target* now has dunder method to support subtraction, for the targets only, and a `safe_copy` method
- *Notification* object now maintains a list of all the target values selected by deliveries, and this
is archived for debug purposes ( and supports the new unique target value functionality)

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
