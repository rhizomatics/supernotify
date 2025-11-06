# Public releases

## 1.1.4
- Explicit delivery selection in action overrides scenario disablement
- Extended and reorganized documentation
- Suppressed notifications now have a reason recorded, DUPE, SNOOZED, NO_SCENARIO

## 1.1.3
- Move out all people functionality from Context to new PeopleRegistry
- Move runtime model classes out of `__init__.py`
- Add new Target class that holds and filters recipients
- Simplify logic for generating recipients and envelopes
- Experimental new MQTTDeliveryMethod

## 1.1.2

- Remove method options where not relevant - chime, media_image

## 1.1.1

- Options defaulting for methods improved
- Archive checks for MQTT client first, and all file IO aio based

## 1.1.0

- Refactored internal use of dictionaries for delivery config, method defaults and targets to typed classes for easier debugging and testing
- Dupe suppression now alphaizes hashes to avoid notification storms where a counter or timestamp defeats the dupe check
- Actions now separate out target data for service call wherever supported
- MQTT topic archive now works if file archive also switched on

## 1.0.4

- Test fixes, archive logging, and archive publish error handling
- Scenarios, methods and deliveries can be switched on or off via their exposed entities in Home Assistant UI or API
- `NotifyEntityDeliveryMethod` added as pre-production

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
