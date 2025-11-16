[![Rhizomatics Open Source](https://avatars.githubusercontent.com/u/162821163?s=96&v=4)](https://github.com/rhizomatics)

# Supernotify [![hacs][hacsbadge]][hacs]


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
    * Remove repetitive config and code from automations
    * Adaptors automatically tune notification data for each integration
    * For example, use with a [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) to get camera snapshots by e-mail instead of, or as well as, mobile notifications. See the [Frigate Recipe](recipes/frigate_emails.md) for more info.
* Go beyond `notify` integrations
    * Chimes, sirens, SMS, Alexa Announcements and Sounds, API calls, MQTT devices
    * All the standard `notify` and  `notify.group` implementations available, including the modern `NotifyEntity` based ones
    * Greatly simplified use of Mobile Push notifications, e.g. for iPhone
    * Standard HomeAssistant behaviour, including data templating and `notify.group`
* Conditional Notifications
    * Using standard Home Assistant `condition`
    * Extra condition variables added, including message and priority
    * Combine with occupancy detection to easily tune notifications based on who is in, message priority, even the content of the message
* **Scenarios** for simple concise configuration
    * Package up common chunks of config and conditional logic
    * Have them applied on-demand in actions (`red_alert`,`nerdy`) or automatically based on conditions (`everyone_home_day`,`frigate_person`).
    * See the [Alexa Whispering](recipes/alexa_whisper.md), [Home Alone](recipes/home_alone.md) and [Bedtime](recipes/bedtime.md) for simple to use examples.
* Unified Person model
    * Currently missing from Home Assistant.
    * Define an email, SMS number or mobile device, and then use the `person` entity in notification actions, Supernotify works out which attribute to use where
    * See [People](people.md) for more info
* Easy **HTML email templates**
    * Standard HomeAssistant Jinja2, defined in YAML config, action calls or as stand-alone files in the `config` director
    * Default general template supplied
* **Mobile Actions**
    * Set up a single set of consistent mobile actions across multiple notifications and reuse across many notifications
    * Include *snoozing* actions to silence based on criteria
* Flexible **Image Snapshots**
    * Supports cameras, MQTT Images and image URLs.
    * Reposition cameras to PTZ presets before and after a snapshot is taken, including special support for Frigate PTZ presets
    * See the [Multimedia](multimedia.md) documentation for more information.
* Choose Your Level Configuration
    * Set defaults, including lists of targets at
      - Transport level, for example `alexa_devices`
      - Delivery level, for example `Alexa Announce`,`Alexa Speak`
      - On the Action call for each notification
      - On a Scenario to apply to arbitrary deliveries
* **Duplicate Notification** Suppression
    * Tune how long to wait before re-allowing
    *  Can be combined with snoozing for specific people or transports
* Notification **Archival** and **Debug Support**
    * Optionally archive notifications to file system and/or MQTT topic
    * Includes full debug information, including occupancy assumptions, delivery and target selections
    * HomeAssistant Actions ( previously known as services ) to pull back live configuration or last known notification details.
    * Deliveries, Transports and Scenarios exposed as entities, and can be examined and switched on/off via the Home Assistant UI

## Installation

* Make sure you have HACS available
    - If not, check the [HACS Instructions](https://hacs.xyz/docs/use/)
    - Supernotify is one of the default repositories in HACS so no other configuration required
* Select *SuperNotify* in the list of available integrations in HACS and install
* Add a `notify` config for the `supernotify` integration,
    * See `examples` directory for working minimal and maximal configuration examples.
* Extra config for email attachments
    * To use attachments, e.g. from camera snapshot or a `snapshot_url`, you must set the `allowlist_external_dirs` in main HomeAssistant config to the same as `media_path` in the supernotify configuration


## Getting Started

The best place to start are the [Recipes](recipes/index.md), which show how some popular,
and advanced, configuration can be achieved.

Otherwise, start with the simplest possible config, like the [minimal](examples/config_notify/minimal.md) example.

Calls to supernotify look like any other notify action, which will work but not use any of the features:

### Minimal
```yaml
  - action: notify.supernotify
    data:
        title: Security Notification
        message: Something went off in the basement
```

That simple call can be enriched in a few ways, here with a message template (as in
regular notify), using `person_id` targets to derive email,  applying some pre-built
scenarios, and adding a click action to the mobile push notifications.

### More features
```yaml
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

 Lots more ideas in the [Recipes](recipes/index.md) for more ideas.

## Core Concepts

### Transport

- *Transport* is the underlying platform that performs notifications.
- They make the difference between regular Notify Groups and Supernotify. While a Notify Group
seems to allow easy multi-channel notifications, in practice each notify transport has different `data` (and `data` inside `data`!) structures, addressing etc so in the end notifications have to be simplified to the lowest common set of attributes, like just `message`!
- Supernotify comes out the box with adapters for common transports, like e-mail, mobile push, SMS, and Alexa, and a *Generic* transport that can be used to wrap any other Home Assistant action
- The transport adapter is what allows a single notification to be sent to many platforms, even
when they all have different and mutually incompatible interfaces. They adapt notifications to the transport, pruning out attributes they can't accept, reshaping `data` structures, selecting just the appropriate targets, and allowing additional fine-tuning where its possible.
- Transports can optionally be defined in the Supernotify config with defaults
- See [Transports](transports/index.md) for more detail

### Delivery

- A **Delivery** defines each notification channel you want to use
- While Supernotify comes with many transports, only the ones you define with a Delivery will
get used to send notifications, with the exception of *Notify Entity* transport which is
always on unless switched off.
- Deliveries allow lots of fine tuning and defaults to be made, and you can also have multiple
deliveries for a single transport, for example a `plain_email` and `html_email` deliveries.
- See [Deliveries](deliveries.md) and [Recipes](recipes/index.md) for more detail

### Scenario
- An easy way to package up common chunks of config, optionally combined with conditional logic
- Scenarios can be manually selected, in an `apply_scenarios` value of notification `data` block,
or automatically selected using a standard Home Assistant `condition` block.
- They make it easy to apply overrides in one place to many different deliveries or notifications,
and are the key to making notification calls in your automations radically simpler
- See [Scenarios](scenarios.md) and [Recipes](recipes/index.md) for more detail


### Target
- The target of a notification.
- This could be a *direct* target, like an `entity_id`, `device_id`,
e-mail address, phone number, or some custom ID for a specialist transport like Telegram or API calls.
- It also has some support, more to come, for *indirect* targets. The primary one is `person_id`,
although some other Home Assistant ones will be supported in future, like `label_id`,`floor_id`
and `area_id`.
- There's also the in-between type, *group*, which is sort of both indirect and direct. Supernotify
    will exploded these for the *Chime* integration, but otherwise ignore them.

### Recipient
- Define a person, with optional e-mail address, phone number, mobile devices or custom targets.
- This lets you target notifications to people in notifications, and each transport will pick the type
of target it wants, for example the SMS one picking phone number and the SMTP one an e-mail address
- See [People](people.md) and [Recipes](recipes/index.md) for more detail

!!! info
    For the technically minded, there's a [Class Diagram](developer/class_diagram.md) of the core ones.

## Core Principles

1. All a notification needs is a message, everything else can be defaulted, including all the targets
2. If you define something in an action call, it takes precedence over the defaults
   - This can be tuned by things like `target_usage`
   - The people registry is only used to generate targets if no targets given
3. Action > Scenario > Delivery > Transport for configuration and defaults


## Flexible Configuration

Delivery configuration can be done in lots of different ways to suit different configurations
and to keep those configuration as minimal as possible.

### Priority order of configuration application

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


[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
