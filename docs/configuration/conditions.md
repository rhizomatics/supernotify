---
tags:
  - condition
  - template
---
# Conditions

The [Bedtime](../recipes/bedtime.md) recipe illustrates a simple use of conditions, based on time of day, and [Seasonal Greetings](../recipes/seasonal_greetings.md) shows a slightly more complex version with `or` logic for date ranges. These conditions are identical to what can be used in any Home Assistant automation.


## Condition Variables

`Scenario` and `Transport` conditions have access to everything that any other Home Assistant conditions can access, such as entities, templating etc. In addition, Supernotify makes additional variables
automatically available:

|Template Variable              |Description                                                       |
|-------------------------------|------------------------------------------------------------------|
|notification_priority          |Priority of current notification, explicitly selected or default  |
|notification_message           |Message of current notification                                   |
|notification_title             |Title of current notification                                     |
|applied_scenarios              |Scenarios explicitly selected in current notification call        |
|required_scenarios             |Scenarios a notification mandates to be enabled or else suppressed|
|constrain_scenarios            |Restricted list of scenarios                                      |
|occupancy                      |One or more occupancy states, e.g. ALL_HOME, LONE_HOME            |

These recipes demonstrate how the template variables can be used:

* [Content Escalation](../recipes/content_escalation.md)
* [Alexa Whisper](../recipes/alexa_whisper.md)
* [Except Scenario](../recipes/except_scenario.md)


## References

* [Home Assistant Conditions](https://www.home-assistant.io/docs/scripts/conditions/)
