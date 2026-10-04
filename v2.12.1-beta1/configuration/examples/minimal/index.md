# Minimal Configuration

Source: https://supernotify.rhizomatics.org.uk/latest/configuration/examples/minimal/

The smallest possible setup no longer needs any YAML at all: go to **Settings → Devices & Services → Add Integration**, search for **Supernotify**, and accept the defaults. Mobile push, an existing SMTP integration or notify entities, and recipients from Home Assistant persons are all discovered automatically - see [Getting Started](https://supernotify.rhizomatics.org.uk/latest/getting_started/index.md).

```yaml
 # There is no longer any minimal YAML since the core configuration
 # can all be set up from the Home Assistant Integrations screen
```

YAML is still how [Deliveries](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/index.md), transports, scenarios, recipients and cameras are configured - see the [Maximal Configuration](https://supernotify.rhizomatics.org.uk/latest/configuration/examples/maximal/index.md) example for that.
