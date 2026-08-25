---
tags:
  - config
  - examples
description: The smallest way to get Supernotify running - now via the UI, not YAML
---
# Minimal Configuration

The smallest possible setup no longer needs any YAML at all: go to **Settings → Devices &
Services → Add Integration**, search for **Supernotify**, and accept the defaults. Mobile push,
an existing SMTP integration or notify entities, and recipients from Home Assistant persons are
all discovered automatically - see [Getting Started](../../getting_started.md).

```yaml
--8<-- "examples/minimal.yaml"
```

YAML is still how [Deliveries](../deliveries.md), transports, scenarios, recipients and cameras
are configured - see the [Maximal Configuration](maximal.md) example for that.
