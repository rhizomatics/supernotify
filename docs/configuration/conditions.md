# Conditions

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

## References

* [Home Assistant Conditions](https://www.home-assistant.io/docs/scripts/conditions/)