---
tags:
  - configuration
  - yaml
---
# YAML

By default, advanced configuration - `delivery`, `transports`, `scenarios`, `recipients`, `cameras`, `action_groups`, `links` and `snooze` - lives in `configuration.yaml`, under a top-level `supernotify` section, or split out, see below. Everything else (template/media paths, archive, duplicate detection, housekeeping, and the action name) is managed entirely from the Integrations web page - see [Getting Started](../getting_started.md).

## Naming the Integration

By default every automation calls the action `notify.supernotify` for Notify compatibility or `supernotify.notify` for friendlier UI. If you need a different name (for example to match existing automations), set it from the Integrations page: **Settings → Devices & Services → Supernotify → Configure**, or during initial setup. This is the only place the name is set - it is not a YAML key.

## Splitting Out YAML

Many people move chunks of config out of `configuration.yaml` to make it more manageable, since the main file can get huge.

In this example, all the notify configuration lives in a separate file in the same directory called `supernotify.yaml`. Alternatively, create a sub-directory to keep it neater.

```yaml title='configuration.yaml'
supernotify: !include supernotify.yaml
```

## Migrating from an older `notify:` platform block

Older versions configured everything - including delivery/transports/scenarios/etc - under a legacy `notify:` platform block:

```yaml
notify:
  - name: Supernotify
    platform: supernotify
    delivery:
      ...
```

That form is no longer read. If Home Assistant still finds one, a repair appears in
**Settings → System → Repairs** offering to migrate it automatically: it writes a
`supernotify.yaml` file with your delivery/transports/scenarios/recipients/cameras/action_groups/links/snooze settings and adds the `supernotify: !include supernotify.yaml` line above to `configuration.yaml` for you, reloading immediately (no restart needed). A `name:` in the old block is preserved as the Integration's configured name automatically, independent of whether you run this repair.

You can just as easily do this move by hand instead of using the repair - either way works. Either way, the old `notify:` block itself is left in place and simply ignored; delete it yourself once you're happy the new configuration works. The repair keeps reappearing (and the old block stays harmless either way) until you do - once it's gone, the repair clears itself automatically on the next restart.
