---
tags:
  - configuration
  - yaml
---
# YAML

By default, configuration lives in `config.yaml`, under a `notify` section. 

## Naming the Integration

Every integration has a name of your choice:

```yaml
- name: Supernotify
  platform: supernotify
```

In this example, with the name `Supernotify` every automation should call the action `notify.supernotify`

This is the name used in all the documentation, although you can make it almost anything else you like.

## Splitting Out YAML

Many people move chunks of config out of `config.yaml` to make it more manageable, since the main file can get huge.

In this example, all the notify configuration lives in a separate file in the same directory called `notify.yaml`.

```yaml title='config.yaml'
notify: !include notify.yaml
```
