---
tags:
  - delivery
  - recipe
description: Define a Supernotify delivery with a fixed list of targets which will not be changed by activated scenarios or manually defined targets in a Home Assistant action call
---
# Recipe - Fixed Targets

## Purpose

A delivery has its own special list of targets, which must not be overridden by
anything else, including explicit targets set in a notification action call.

## Implementation

Define a target on the `delivery` configuration, and set the `target_usage` to `fixed`,
so these addresses are fixed and not overridden.

## Example Configuration
```yaml
  delivery:
    my_vanilla_alert:
      transport: generic
      action: script.alert_call
      delivery_defaults:
          target_usage: fixed
          target:
              - switch.buzzer_1
              - switch.buzzer_3

```

## Variations

### Other transports

This will work identically for any transport, there's nothing generic specific in how it works
