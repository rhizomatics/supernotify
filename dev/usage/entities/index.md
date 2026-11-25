# Entities

Source: https://supernotify.rhizomatics.org.uk/latest/usage/entities/

Supernotify adds these entities to Home Assistant. Apart from the recipients' notify entities, they all belong to a single *SuperNotify* device, on the integration's page. Supernotify is a service, not a device integration, so the same entities are available whatever phones, speakers or other devices notifications go to.

## Notify

| Entity             | What it does                                                                                                                                                                                                                                                                                                                                                         |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Notify *recipient* | One for each recipient. Sending a message to it notifies that recipient, with all their usual deliveries, occupancy, scenarios, snoozes and duplicate checks applied. Only a message and title can be given, as for any notify entity; use the [`supernotify.notify`](https://supernotify.rhizomatics.org.uk/latest/usage/actions/index.md) action for anything more |

## Switches

Each switch turns something on or off at runtime, overriding its `enabled` in the configuration. The override is kept across a restart or reload, until the configured value itself changes. The *Reset overrides* button puts them all back. All are configuration entities.

| Entity                        | What it does                                                                |
| ----------------------------- | --------------------------------------------------------------------------- |
| Scenario *scenario*           | Whether the scenario is enabled, and so able to apply to notifications      |
| Recipient *recipient* Enabled | Whether the recipient is enabled, and so able to be notified                |
| Delivery *delivery* Enabled   | Whether the delivery is enabled, and so able to be used for notifications   |
| *Transport* Enabled           | Whether the transport is enabled. When off, none of its deliveries are used |

## Binary Sensors

All are diagnostic entities.

| Entity                        | What it shows                                                                                                                                                                                                                                                                                                                          |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scenario Condition *scenario* | Whether the scenario's conditions hold right now, evaluated at medium priority with the current occupancy. Read only: whether the scenario is enabled is its switch. It is *unknown* if `scenario_control` has `refresh` switched off, see [Scenarios](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/index.md) |
| Scenario Manual *scenario*    | For a scenario with no conditions of its own. This one is the control: a script or automation sets it on or off, and the scenario applies while it's on. Kept across a restart                                                                                                                                                         |
| Recipient *recipient*         | Whether the recipient is enabled. Deprecated, use the recipient's switch                                                                                                                                                                                                                                                               |
| Delivery *delivery*           | Whether the delivery is enabled. Deprecated, use the delivery's switch, and disabled unless switched on                                                                                                                                                                                                                                |
| Transport *transport*         | Whether the transport is enabled. Deprecated, use the transport's switch, and disabled unless switched on                                                                                                                                                                                                                              |

## Sensors

Both are diagnostic entities, counting up from when Supernotify was installed, and kept across a restart.

| Entity                | What it counts                                                                                                                                                                                                                                   |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Notifications sent    | Notifications delivered by at least one delivery. A notification with `dry_run` isn't counted                                                                                                                                                    |
| Notification failures | Notifications that stopped with an unexpected error. A delivery failing, or a notification skipped by a rule such as a snooze, isn't counted, see [Troubleshooting](https://supernotify.rhizomatics.org.uk/latest/help/troubleshooting/index.md) |

## Button

| Entity          | What it does                                                                                                                                                                                    |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reset overrides | Puts every scenario, recipient, delivery and transport switched on or off at runtime back to its configured state, the same as the `supernotify.reset_overrides` action. A configuration entity |

## How Entities Update

Supernotify doesn't poll anything, and has no requests to an outside service to update its entities, so no rate limits or quotas apply. Its entities change when something happens:

- The **switches** change when switched, or when *Reset overrides* is pressed or the configuration changes
- The **Scenario Condition** binary sensors are evaluated again straight away when an entity in their conditions changes state, and once a minute for conditions that depend on the time or date, or on something Home Assistant can't track. Both are set in `scenario_control`, see [Scenarios](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/index.md)
- The **counters** change as each notification is sent
- **Recipient**, **delivery** and **transport** binary sensors change with their switches

The `supernotify.refresh_entities` [action](https://supernotify.rhizomatics.org.uk/latest/usage/actions/index.md) publishes the state of every entity again, if one ever looks out of date.
