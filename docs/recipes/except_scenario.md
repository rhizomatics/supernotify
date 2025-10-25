# Recipe - Except Scenario

## Purpose

Skip notifications if its already being handled by a specific scenario

## Implementation

Uses a **Scenario** condition. The list of scenarios applied to the notification
is exposed as a template (Jinja2) variable, so can be used in tests.

## Example Configuration

```yaml
red_alert:
      alias: make a fuss for critical priority, unless its an unknown vehicle
      condition:
        condition: and
        conditions:
          - "{{notification_priority in ['critical']}}"
          - "{{'unknown_vehicle' not in applied_scenarios}}"

```

## Variations

The applied scenario could be one explicitly referenced in the notify action `data` section
or it could be one that is automatically enabled, for example based on date/time, occupancy,
alarm state or similar.
