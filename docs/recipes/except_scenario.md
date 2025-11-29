---
tags:
  - scenario
  - templating
  - recipe
  - condition
---
# Recipe - Except Scenario

## Purpose

Skip notifications if its already being handled by a specific scenario

## Implementation

Uses a **Scenario** condition. The list of scenarios applied to the notification is exposed as a template (Jinja2) variable, so can be used in tests.

## Example Configuration

```yaml
scenarios:
  red_alert:
        alias: make a fuss for critical priority, unless its an unknown vehicle
        conditions:
            - "{{notification_priority in ['critical']}}"
            - "{{'unknown_vehicle' not in applied_scenarios}}"

```
