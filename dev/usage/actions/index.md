# Actions

Note

Until 2025, *Actions* were known as **Services** in Home Assistant, and that is still commonly used. In this documentation, the new term 'Action' is always used. To avoid ambiguity, when the quite different actions in Actionable Notifications are referred to, it is always as "Mobile Actions"

## Available Actions

To use any of these, prefix with `supernotify.`. Try them out via [Tools](https://www.home-assistant.io/docs/tools/dev-tools/)

| Action                         | Description                                                                                                          |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| notify                         | The best way to send a notification. The UI has much more help on choosing options than calling `notify.supernotify` |
| reload                         | Reload all the supernotify config yaml and restart the component with the fresh config                               |
| enquire_deliveries_by_scenario | List the deliveries which will be used per configured scenario                                                       |
| enquire_last_notification      | Show the details, including debug info, for the last handled notification                                            |
| enquire_implicit_deliveries    | List all the configured default delivieries                                                                          |
| enquire_scenarios              | List all the configured scenarios                                                                                    |
| enquire_active_scenarios       | Compute all the scenario conditions and list which apply right now                                                   |
| enquire_occupancy              | List all the recipients by whether in or out                                                                         |
| enquire_snoozes                | List all the active snoozes                                                                                          |
| refresh_entities               | Re-publish the current state of every SuperNotify entity                                                             |
| reset_overrides                | Put scenarios, recipients, deliveries and transports switched on or off back as configured, or only one `kind`       |
| clear_snoozes                  | Clear all active snoozes                                                                                             |
| purge_archive                  | Force the archive housekeeping to run immediately and remove old notification records                                |
| purge_media                    | Force the media storage housekeeping to run immediately and remove old media                                         |
| snooze                         | Snooze notifications for a delivery or target                                                                        |

The same reset as `reset_overrides` with no `kind` is also available as the **Reset overrides** button (`button.supernotify_reset_overrides`) on the SuperNotify device.
