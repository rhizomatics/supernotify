[![Rhizomatics Open Source](https://avatars.githubusercontent.com/u/162821163?s=96&v=4)](https://github.com/rhizomatics)

# Supernotify

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)


Easy multi-channel rich notifications.

An extension of HomeAssistant's built in `notify.notify` that can greatly simplify multiple notification channels and
complex scenarios, including multi-channel notifications, conditional notifications, mobile actions, chimes and template based HTML emails. Can substitute directly for existing notifications to mobile push, email, etc.

## Features

* Send out notifications on multiple channels from one call, removing repetitive config and code from automations
* Standard `notify` implementation so easy to switch out for other notify implementations, or `notify.group`
* Conditional notification using standard Home Assistant `condition` config
* Reuse chunks of conditional logic as *scenarios* across multiple notifications
* Streamlined conditionals for selecting channels per priority and scenario, or
for sending only to people in or out of the property
* Use `person` for all notification configuration, regardless of channel
  * Unified Person model currently missing from Home Assistant
* HTML email templates, using Jinja2, with a general default template supplied
* Single set up of consistent mobile actions across multiple notifications
* Flexible image snapshots, supporting cameras, MQTT Images and image URLs.
  * Cameras can be repositioned using PTZ before and after a snapshot is taken.
  * See the [Multimedia](multimedia.md) documentation for more information.
* Defaulting of targets and data in static config, and overridable at notification time
* Generic support for any notification method
  * Plus canned delivery methods to simplify common cases, especially for tricky ones like Apple Push
* Reloadable configuration
* Tunable duplicate notification detection
* Well-behaved `notify` extension, so can use data templating, `notify.group` and other notify features.
* Refactor out repetitive configuration for ease of maintenance
* Debugging support,
  * Optional archival of message structures to file system and/or MQTT topic
  * Additional actions ( previously known as services ) to pull back live configuration or last known notification details.

## Installation

* Add the [Supernotif Git Repo](https://github.com/rhizomatics/supernotify) to HACS as custom repo
* Select *SuperNotify* in the list of available integrations in HACS and install
* Add a `notify` config for the `supernotify` integration,
    * See `examples` directory for working minimal and maximal configuration examples.
* Extra config for email attachments
    * To use attachments, e.g. from camera snapshot or a `snapshot_url`, you must set the `allowlist_external_dirs` in main HomeAssistant config to the same as `media_path` in the supernotify configuration


## Usage

### Minimal
```yaml
  - action: notify.supernotifier
    data:
        title: Security Notification
        message: '{{state_attr(sensor,"friendly_name")}} triggered'
```

### More features
```yaml
  - action: notify.supernotifier
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
        constrain_scenarios:
        delivery:
            mobile_push:
                data:
                    clickAction: https://my.home.net/dashboard

```
Note here that the `clickAction` is defined only on the `mobile_push` delivery. However
its also possible to define everything at the top level `data` section and let the individual
deliveries pick out the attributes they need. This is helpful either if you don't care about
fine tuning delivery configurations, or using existing notification blueprints, such as the popular
[Frigate Camera Notification Blueprints](https://github.com/SgtBatten/HA_blueprints/tree/main/Frigate%20Camera%20Notifications).


### Templated
```yaml
  - action: notify.supernotifier
    data:
        message:
    data_template:
        title: Tank Notification
        message:  "Fuel tank depth is {{ state_attr('sensor.tank', 'depth') }}"
        data:
            priority: {% if {{ state_attr('sensor.tank', 'depth') }}<10 }critical{% else %}medium {% endif %}
```

 See the [Recipes](recipes/index.md) for more ideas.

## Delivery Methods

*Delivery Methods* are the basic difference between regular Notify Groups and Supernotify. While a Notify Group
seems to allow easy multi-channel notifications, in practice each notify transport has different `data` (and `data` inside `data`!) structures, addressing etc so in the end notifications have to be simplified to the lowest common set of attributes, like just `message`.

Delivery Methods adapt notifications to the transport, pruning out attributes they can't accept, reshaping `data` structures, selecting just the appropriate targets, and allowing additional fine-tuning where its possible.

See [Delivery Methods](methods.md) page for the full list and more detail on each.

## Flexible Configuration

Delivery configuration can be done in lots of different ways to suit different configurations
and to keep those configuration as minimal as possible.

Priority order of application


| Where                                | When            | Notes                                            |
|--------------------------------------|-----------------|--------------------------------------------------|
| Action Data                          | Runtime call    |                                                  |
| Recipient delivery override          | Runtime call    |                                                  |
| Scenario delivery override           | Runtime call    | Multiple scenarios applied in no special order   |
| Delivery definition                  | Startup         | `message` and `title` override Action Data      |
| Method defaults                      | Startup         |                                                  |
| Target notification action defaults  | Downstream call |                                                  |


1. Action Data passed at runtime call
2. Recipient delivery override
3. Scenario delivery override
4. Delivery definition
5. Method defaults
6. Target notification action defaults, e.g. mail recipients ( this isn't applied inside Supernotify )


## Scenarios

Scenarios are the key to efficient and concise configuration of finely tuned notifications
to suit your house and family.

Its easy to add a scenario or two to a minimal configuration, or go all in and have everything
completely scenario controlled, so that notifications which don't match a scenario get dropped.

See the [Scenarios](scenarios.md) page for more detail.

## Condition Variables

`Scenario` and `DeliveryMethod` conditions have access to everything that any other Home Assistant conditions can
access, such as entities, templating etc. In addition, Supernotify makes additional variables
automatically available:

|Template Variable              |Description                                                       |
|-------------------------------|------------------------------------------------------------------|
|notification_priority          |Priority of current notification, explicitly selected or default  |
|notification_message           |Message of current notification                                   |
|notification_title             |Title of current notification                                     |
|applied_scenarios              |Scenarios explicitly selected in current notification call        |
|required_scenarios             |Scenarios a notification mandates to be enabled or else suppressed|
|constrain_scenarios            |Restricted list of scenarios                                      |
|occupancy                      |One or more occupancy states, e.g. ALL_HOME, LONE_HOME            |
