---
tags:
  - configuration
  - yaml
---
# YAML

By default, advanced configuration lives in `configuration.yaml`, under a `supernotify` section ( the basic configuration is all managed entirely by Home Assistant and configured from the Integrations web page ), or split out, see below.

## Naming the Integration

Every integration has a name of your choice:

```yaml
- name: Supernotify
  platform: supernotify
```

In this example, with the name `Supernotify` every automation should call the action `notify.supernotify`

This is the name used in all the documentation, although you can make it almost anything else you like.

## Splitting Out YAML

Many people move chunks of config out of `configuration.yaml` to make it more manageable, since the main file can get huge.

In this example, all the notify configuration lives in a separate file in the same directory called `supernotify.yaml`. Alternatively, create a sub-directory to keep it neater.

```yaml title='configuration.yaml'
supernotify: !include supernotify.yaml
```
