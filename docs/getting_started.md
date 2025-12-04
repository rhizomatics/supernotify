---
tags:
  - installation
  - hacs
  - configuration
description: Getting Started with Supernotify for Home Assistant
---
# Getting Started

## Installation

* Make sure you have HACS available
    - If not, check the [HACS Instructions](https://hacs.xyz/docs/use/)
    - Supernotify is one of the default repositories in HACS so no custom repo configuration required
* Select *SuperNotify* in the list of available integrations in HACS and *Download*
* Add Supernotify to the Home Assistant YAML configuration
    * By default this is `config.yaml`, unless you have an `include` statement to move notify platform to another file
* Add a `notify` config for the `supernotify` integration
    * Give it a `name`, *"supernotify"* is a good choice but it can be anything
        * You will refer to this on every automation call, for example the action `notify.supernotify`
    * See `examples` directory for working [minimal](configuration/examples/minimal.md) and [maximal configuration](configuration/examples/maximal.md) examples.
* If using email attachments,  e.g. from camera snapshot or a `snapshot_url`, some extra config needed:
    * Configure a valid `media_path` in the Supernotify config, usually somewhere under `/config`
    * Set the `allowlist_external_dirs` in main HomeAssistant config to the same as `media_path` in the Supernotify configuration

## Configuration

Otherwise, start with the simplest possible config, like the [minimal](configuration/examples/minimal.md) example.

By default, configuration lives in `config.yaml`, under a `notify` section. Many people move chunks of config out of here to make it more manageable, like this, so all the notify configuration lives in one file, in this case `notify.yaml`.

```yaml
notify: !include notify.yaml
```

[Deliveries](configuration/deliveries.md) explains how to set up the basic notification channels you want, and [Configuration Levels](configuration//levels.md) how to choose the best place to put configuration for simplicity, clarity and concision. The [Recipes](recipes/index.md) show how some popular, and advanced, configuration can be achieved.


## Calling the Supernotify Action

In your automations, scripts etc, make calls to Supernotify as any other notify action, with a `message` and an optional `title`. You can also include any of the newer style *Notify Entities* in the target. For many cases, you can convert an existing notification call to Supernotify by only changing the `action` name.

```yaml title="Example Action Call"
  - action: notify.supernotify
    data:
        title: Security Notification
        message: Something went off in the basement
```

That simple call can be enriched in a few ways, here with a message template (as in
regular notify), using `person_id` targets to derive email,  applying some pre-built
scenarios, and adding a click action to the mobile push notifications.

```yaml title="More Advanced Action Call"
  - action: notify.supernotify
    data:
        title: Security Notification
        message: '{{state_attr(sensor,"friendly_name")}} triggered'
        target:
          - person.jim_bob
          - person.neighbour
        priority: high
        apply_scenarios:
          - home_security
          - garden
        delivery:
            mobile_push:
                data:
                    clickAction: https://my.home.net/dashboard

```
Note here that the `clickAction` is defined only on the `mobile_push` delivery. However
it is also possible to simply define everything at the top level `data` section and let the individual
transport adaptors pick out the attributes they need. This is helpful either if you don't care about
fine tuning delivery configurations, or using existing notification blueprints, such as the popular
[Frigate Camera Notification Blueprints](https://github.com/SgtBatten/HA_blueprints/tree/main/Frigate%20Camera%20Notifications).


```yaml title="Example Action Call Using Templates"
  - action: notify.supernotifier
    data:
        message:
    data_template:
        title: Tank Notification
        message:  "Fuel tank depth is {{ state_attr('sensor.tank', 'depth') }}"
        data:
            priority: {% if {{ state_attr('sensor.tank', 'depth') }}<10 }critical{% else %}medium {% endif %}
```

 Lots more ideas in the [Recipes](recipes/index.md) for more ideas.
