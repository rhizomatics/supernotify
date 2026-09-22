# Configuration

Start with the simplest possible setup, [added from the UI](https://supernotify.rhizomatics.org.uk/latest/getting_started/index.md) with no YAML at all - see the [minimal](https://supernotify.rhizomatics.org.uk/latest/configuration/examples/minimal/index.md) page. This will allow you to notify using *Notify Entities* and push mobile notifications to all the devices registered in Home Assistant, without specifying any targets, or any other config.

This page onwards covers YAML configuration - still how [Deliveries](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/index.md), transports, scenarios, recipients and cameras are set up, though archive, duplicate detection and housekeeping can also be configured from the UI.

[Deliveries](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/index.md) explains how to set up the basic notification channels you want, and [Configuration Levels](https://supernotify.rhizomatics.org.uk/latest/configuration/levels/index.md) how to choose the best place to put configuration for simplicity, clarity and concision.

If using email attachments, e.g. from camera snapshot or a `snapshot_url`, some extra config needed, detailed in [Multimedia Basic Configuration](https://supernotify.rhizomatics.org.uk/latest/configuration/multimedia/#basic-configuration)

## Index

{{ pagetree(siblings) }}

## More

In addition to this reference documentation, see also the sample configuration snippets in the [recipes](https://supernotify.rhizomatics.org.uk/recipes/).
