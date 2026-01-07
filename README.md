![Supernotify](assets/images/dark_icon.png){ align=left }

# Supernotify

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)

 <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=rhizomatics&repository=supernotify" target="_blank" rel="noopener noreferrer">
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Add to HACS">
   </a>
<br/>
<br/>
<br/>

**Easy multi-channel rich notifications.**

An extension of HomeAssistant's built in `notify` platform that can greatly simplify multiple notification channels and complex scenarios, including multi-channel notifications, conditional notifications, mobile actions, camera snapshots, chimes and template based HTML emails.

Supernotify has one goal - to make the **simplest possible notification do as many notifications as you need with no code and minimal configuration**.

This keeps automations, scripts, AppDaemon apps etc simple and easy to maintain, with all the detail and rules managed all in one place, with lots of support to make even complicated preferences easy to manage. The smallest notification possible - only a message defined - can be enough to trigger everything you need to keep everyone informed. Change e-mail addresses in one place, and let Supernotify handle finding which Mobile Apps to use.

With two lines of very simple yaml, start mobile push notifications to everyone registered in the house, without
configuring mobile app names in notifications.

## Distribution

Supernotify is a custom component available via the [Home Assistant Community Shop](https://hacs.xyz) (**HACS**) integration. It's free and open sourced under the [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0).

## Documentation

Try [Getting Started](https://supernotify.rhizomatics.org.uk/getting_started/), the explanation of [core concepts](https://supernotify.rhizomatics.org.uk/concepts/), and the available [transport adaptors](https://supernotify.rhizomatics.org.uk/transports/) to understand what it can do. [Notifying](usage/notifying.md) shows how to call Supernotify from automations or the Developer Tools action page.

There are lots of [recipes](https://supernotify.rhizomatics.org.uk/recipes/) with sample
config snippers to give you some more ideas, or browse by [tags](https://supernotify.rhizomatics.org.uk/tags/).


## Features

* One Action -> Multiple Notifications
    * Remove repetitive config and code from automations
    * Adaptors automatically tune notification data for each integration
    * For example, use with a [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) to get camera snapshots by e-mail instead of, or as well as, mobile notifications. See the [Frigate Recipe](https://supernotify.rhizomatics.org.uk/recipes/frigate_emails/) for more info.
* Automated set-up
    * Delivery configuration for Mobile Push, Email (SMTP) and Notify Entity set up automatically
    * Mobile Apps automatically discovered, including Manufacturer and Model of the phone, which can be used to customize delivery
    * Alexa Devices for sending chime noises automatically discovered from Home Assistant
* Go beyond `notify` integrations
    * Chimes, sirens, SMS, TTS, Alexa Announcements and Sounds, API calls, MQTT devices
    * All the standard `notify` and  `notify.group` implementations available, including the modern `NotifyEntity` based ones
    * Greatly simplified use of Mobile Push notifications, e.g. for iPhone
    * Standard HomeAssistant behaviour, including data templating and `notify.group`
* Conditional Notifications
    * Using standard Home Assistant `conditions`
    * Extra condition variables added, including message and priority
    * Combine with occupancy detection to easily tune notifications based on who is in, message priority, even the content of the message
* **Scenarios** for simple concise configuration
    * Package up common chunks of config and conditional logic
    * Have them applied on-demand in actions (`red_alert`,`nerdy`) or automatically based on conditions (`everyone_home_day`,`frigate_person`).
    * See the [Alexa Whispering](https://supernotify.rhizomatics.org.uk/recipes/alexa_whisper/), [Home Alone](https://supernotify.rhizomatics.org.uk/recipes/home_alone/) and [Bedtime](https://supernotify.rhizomatics.org.uk/recipes/bedtime/) for simple to use examples.
* Unified Person model
    * Currently missing from Home Assistant.
    * Define an email, SMS number or mobile device, and then use the `person` entity in notification actions, Supernotify works out which attribute to use where
    * People are auto-configured along with their mobile apps based on existing Home Assistant configuration
    * See [People](https://supernotify.rhizomatics.org.uk/people/) for more info
* Easy **HTML email templates**
    * Standard HomeAssistant Jinja2, defined in YAML config, action calls or as stand-alone files in the `config` director
    * Default general template supplied
* **Mobile Actions**
    * Set up a single set of consistent mobile actions across multiple notifications and reuse across many notifications
    * Include *snoozing* actions to silence based on criteria
* Flexible **Image Snapshots**
    * Supports cameras, MQTT Images and image URLs.
    * Reposition cameras to PTZ presets before and after a snapshot is taken, including special support for Frigate PTZ presets
    * See the [Multimedia](https://supernotify.rhizomatics.org.uk/multimedia/) documentation for more information.
* Choose Your Level Configuration
    * Set defaults, including lists of targets at
      - Transport Adaptor level, for example `alexa_devices`
      - Delivery level, for example `Alexa Announce`,`Alexa Speak`
      - On the Action call for each notification
      - On a Scenario to apply to arbitrary deliveries
* **Duplicate Notification** Suppression
    * Tune how long to wait before re-allowing
    *  Can be combined with snoozing for specific people or transports
* Notification **Archival** and **Debug Support**
    * Optionally archive notifications to file system and/or MQTT topic
    * Includes full debug information, including occupancy assumptions, delivery and target selections
    * HomeAssistant Actions ( previously known as services ) to pull back live configuration or last known notification details. See [Actions](usage/actions.md)
    * Deliveries, Transports, Recipients and Scenarios exposed as entities, and can be examined and switched on/off via the Home Assistant UI

## Some YAML Needed

Presently Supernotify supports only [YAML based configuration](configuration/yaml.md). UI based config will be added, though YAML will be preserved for ease of working with larger rule bases.

You can however do a lot with only 2 lines of copy-paste config, using the [example configurations](configuration/examples/minimal.md) and [recipes](recipes/index.md) in the documentation - that's enough to do this:

```yaml title="With the default 2 lines of YAML"
  - action: notify.supernotify
    data:
        message: Hello! Testing this new Supernotify thing sending to everyone's mobile apps
```

## Also From Rhizomatics

- [updates2mqtt](https://updates2mqtt.rhizomatics.org.uk) - Automatically update self-hosted Docker containers via Home Assistant's Updates UI, or any other MQTT consumer
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Automate state transitions for Home Assistant alarm control panels
- [awesome-mqtt](https://github.com/rhizomatics/awesome-mqtt) -  Curated list of MQTT resources


[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
