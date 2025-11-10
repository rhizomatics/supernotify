[![Rhizomatics Open Source](https://avatars.githubusercontent.com/u/162821163?s=96&v=4)](https://github.com/rhizomatics)

# Supernotify

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)


**Easy multi-channel rich notifications.**

An extension of HomeAssistant's built in `notify` platform that can greatly simplify multiple notification channels and complex scenarios, including multi-channel notifications, conditional notifications, mobile actions, chimes and template based HTML emails.

Supernotify lets you make a simple, single notification action from
all your automations, scripts, AppDaemon apps etc and have all the detail and rules managed all in one place, with lots of support to make even complicated preferences easy to manage.

!!! warning

    Presently Supernotify supports only YAML based configuration. UI based config will be added, however YAML will be preserved for ease of working with larger rule bases.

    You can however do a lot with very little config, using the example configurations and recipes in the documentation.


## Features

* One Action -> Multiple Notifications
  - Remove repetitive config and code from automations
  - Adaptors automatically tune notification data for each integration
  - For example, use with a [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) to get camera snapshots by e-mail instead of, or as well as, mobile notifications. See the [Frigate Recipe](recipes/frigate_emails.md) for more info.
* Go beyond `notify` integrations
  - Chimes, sirens, SMS, Alexa Announcements and Sounds, API calls, MQTT devices
  - All the standard `notify` and  `notify.group` implementations available, including the modern `NotifyEntity` based ones
  - Greatly simplified use of Mobile Push notifications, e.g. for iPhone
  - Standard HomeAssistant behaviour, including data templating and `notify.group`
* Conditional Notifications
  - Using standard Home Assistant `condition`
  - Extra condition variables added, including message and priority
  - Combine with occupancy detection to easily tune notifications based on who is in, message priority, even the content of the message
* **Scenarios** for simple concise configuration
  - Package up common chunks of config and conditional logic
  - Have them applied on-demand in actions (`red_alert`,`nerdy`) or automatically based on conditions (`everyone_home_day`,`frigate_person`).
  - See the [Alexa Whispering](recipes/alexa_whisper.md), [Home Alone](recipes/home_alone.md) and [Bedtime](recipes/bedtime.md) for simple to use examples.
* Unified Person model
  - Currently missing from Home Assistant.
  - Define an email, SMS number or mobile device, and then use the `person` entity in notification actions, Supernotify works out which attribute to use where
* Easy **HTML email templates**
  - Standard HomeAssistant Jinja2, defined in YAML config, action calls or as stand-alone files in the `config` director
  - Default general template supplied
* Mobile Actions
  - Set up a single set of consistent mobile actions across multiple notifications and reuse across many notifications
  - Include *snoozing* actions to silence based on criteria
* Flexible Image Snapshots
  - Supports cameras, MQTT Images and image URLs.
  * Reposition cameras to PTZ presets before and after a snapshot is taken, including special support for Frigate PTZ presets
  * See the [Multimedia](multimedia.md) documentation for more information.
* Multi-level configuration
  - Set defaults, including lists of targets at
    - Transport level, for example `alexa_devices`
    - Delivery level, for example `Alexa Announce`,`Alexa Speak`
    - On the Action call for each notification
    - On a Scenario to apply to arbitrary deliveries
* Duplicate Notification Suppression
  - Tune how long to wait before re-allowing
  - Can be combined with snoozing for specific people or transports
* Notification Archival and Debug Support
  * Optionally archive notifications to file system and/or MQTT topic
  * Includes full debug information, including occupancy assumptions, delivery and target selections
  * HomeAssistant Actions ( previously known as services ) to pull back live configuration or last known notification details.
  * Deliveries, Transports and Scenarios exposed as entities, and can be examined and switched on/off via the Home Assistant UI

## Installation

* Add the [Supernotify Git Repo](https://github.com/rhizomatics/supernotify) to HACS as custom repo
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

## Transports

*Transports* are the basic difference between regular Notify Groups and Supernotify. While a Notify Group
seems to allow easy multi-channel notifications, in practice each notify transport has different `data` (and `data` inside `data`!) structures, addressing etc so in the end notifications have to be simplified to the lowest common set of attributes, like just `message`.

Transports adapt notifications to the transport, pruning out attributes they can't accept, reshaping `data` structures, selecting just the appropriate targets, and allowing additional fine-tuning where its possible.

See [Transports](transports.md) page for the full list and more detail on each.

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
| Transport defaults                      | Startup         |                                                  |
| Target notification action defaults  | Downstream call |                                                  |


1. Action Data passed at runtime call
2. Recipient delivery override
3. Scenario delivery override
4. Delivery definition
5. Transport defaults
6. Target notification action defaults, e.g. mail recipients ( this isn't applied inside Supernotify )


## Scenarios

Scenarios are the key to efficient and concise configuration of finely tuned notifications
to suit your house and family.

Its easy to add a scenario or two to a minimal configuration, or go all in and have everything
completely scenario controlled, so that notifications which don't match a scenario get dropped.

See the [Scenarios](scenarios.md) page for more detail.

## Condition Variables

`Scenario` and `Transport` conditions have access to everything that any other Home Assistant conditions can
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
