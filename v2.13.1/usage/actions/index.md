# Actions

Source: https://supernotify.rhizomatics.org.uk/latest/usage/actions/

Note

Until 2025, *Actions* were known as **Services** in Home Assistant, and that is still commonly used. In this documentation, the new term 'Action' is always used. To avoid ambiguity, when the quite different actions in Actionable Notifications are referred to, it is always as "Mobile Actions"

Most of the actions are also usable via [Supernotify Cards](https://github.com/lollox80/supernotify-cards) which provides a rich UI for them.

## Available Actions

To use any of these, prefix with `supernotify.`. Try them out via [Tools](https://www.home-assistant.io/docs/tools/dev-tools/)

| Action                           | Description                                                                                                                                              |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `notify`                         | The best way to send a notification. The UI has much more help on choosing options than calling `notify.supernotify`                                     |
| `enquire_active_scenarios`       | Compute all the scenario conditions and list which apply right now                                                                                       |
| `enquire_archive`                | Search the archived notifications by date or status                                                                                                      |
| `enquire_configuration`          | Retrieve the current config as YAML, merging any advanced YAML config with the Home Assistant UI managed config                                          |
| `enquire_deliveries_by_scenario` | List the deliveries which will be used per configured scenario                                                                                           |
| `enquire_last_notification`      | Show the details, including debug info, for the last handled notification                                                                                |
| `enquire_implicit_deliveries`    | List all the configured default delivieries                                                                                                              |
| `enquire_occupancy`              | List all the recipients by whether in or out                                                                                                             |
| `enquire_scenarios`              | List all the configured scenarios                                                                                                                        |
| `enquire_snoozes`                | List all the active snoozes                                                                                                                              |
| `refresh_entities`               | Re-publish the current state of every SuperNotify entity                                                                                                 |
| `reload`                         | Reload all the supernotify config yaml and restart the component with the fresh config                                                                   |
| `reset_overrides`                | Put scenarios, recipients, deliveries and transports switched on or off back as configured, or only one `kind`                                           |
| `purge_archive`                  | Force the archive housekeeping to run immediately and remove old notification records                                                                    |
| `purge_media`                    | Force the media storage housekeeping to run immediately and remove old media                                                                             |
| `snooze`                         | Snooze notifications for some minutes, see [Snoozing](https://supernotify.rhizomatics.org.uk/latest/usage/snoozing/#snoozing-from-a-script-or-dashboard) |
| `silence`                        | Silence notifications until they are unsnoozed                                                                                                           |
| `unsnooze`                       | Remove a snooze or silence                                                                                                                               |
| `clear_snoozes`                  | Clear all active snoozes                                                                                                                                 |

The same reset as `reset_overrides` with no `kind` is also available as the **Reset overrides** button (`button.supernotify_reset_overrides`) on the SuperNotify device.

### Counts per day from the archive

`enquire_archive` with `verbosity: daily` gives totals for each local day instead of the notifications themselves, for usage charts or a template sensor. Every notification in the range is counted unless a `limit` is given, so a month is a few kilobytes however busy it was.

```yaml
action: supernotify.enquire_archive
data:
  verbosity: daily
  period: last_month
```

```yaml
days:
  - date: "2026-10-04"            # local date, oldest first
    count: 121
    outcome: {success: 58, partial_delivery: 55, dupe: 6, no_delivery: 2}
    priority: {medium: 98, low: 23}
    hour: [3, 1, 0, 0, 0, 0, 2, 5, 9, 11, 8, 7, 9, 12, 10, 6, 5, 4, 3, 2, 1, 2, 1, 1]   # local hour
    deliveries:                   # in how many notifications each delivery sent or failed
      mobile_push: {success: 80, failed: 0}
      alexa_announce: {success: 41, failed: 1}
    scenarios: {afternoon: 40, evening: 22, multi_home: 101}
count: 3100
```
