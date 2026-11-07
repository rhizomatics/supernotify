---
tags:
  - configuration
---
# Configuration

Start with the simplest possible setup, [added from the UI](../quick_start/index.md) with no YAML at all - see the [minimal](examples/minimal.md) page. This will allow you to notify using *Notify Entities* and push mobile notifications to all the devices registered in Home Assistant, without specifying any targets, or any other config.

This page onwards covers configuration - [Deliveries](deliveries.md), scenarios and cameras are set up in YAML, while [recipients](people.md), [transports](../transports/index.md), archive, duplicate detection and housekeeping are configured in the integration.

[Deliveries](deliveries.md) explains how to set up the basic notification channels you want, and [Configuration Levels](levels.md) how to choose the best place to put configuration for simplicity, clarity and concision.

If using email attachments,  e.g. from camera snapshot or a `snapshot_url`, some extra config needed, detailed in [Multimedia Basic Configuration](multimedia.md#basic-configuration)

## Index

{{ pagetree(siblings) }}

## More

In addition to this reference documentation, see also the sample configuration snippets in the [recipes](https://supernotify.rhizomatics.org.uk/recipes/).
