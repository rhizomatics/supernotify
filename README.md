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

Supernotify lets you make a **simple, single notification action** from
all your automations, scripts, AppDaemon apps etc and have all the detail and rules managed all in one place, with lots of support to make even complicated preferences easy to manage.

## Distribution

Supernotify is a custom component available via the [Home Assistant Community Shop](https://hacs.xyz) (**HACS**) integration. It's free and open sourced under the [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0).

## Documentation

For full documentation, go to [https://supernotify.rhizomatics.org.uk](https://supernotify.rhizomatics.org.uk)

## Features

* One Action -> Multiple Notifications
    * Remove repetitive config and code from automations
    * Adaptors automatically tune notification data for each integration
    * For example, use with a [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) to get camera snapshots by e-mail instead of, or as well as, mobile notifications. See the [Frigate Recipe](https://supernotify.rhizomatics.org.uk/recipes/frigate_emails/) for more info.
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
    * See the [Alexa Whispering](https://supernotify.rhizomatics.org.uk/recipes/alexa_whisper/), [Home Alone](https://supernotify.rhizomatics.org.uk/recipes/home_alone/) and [Bedtime](https://supernotify.rhizomatics.org.uk/recipes/bedtime/) for simple to use examples.
* Unified Person model
    * Currently missing from Home Assistant.
    * Define an email, SMS number or mobile device, and then use the `person` entity in notification actions, Supernotify works out which attribute to use where
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
    * HomeAssistant Actions ( previously known as services ) to pull back live configuration or last known notification details.
    * Deliveries, Transports and Scenarios exposed as entities, and can be examined and switched on/off via the Home Assistant UI

## YAML Still Required

Presently Supernotify supports only YAML based configuration. UI based config will be added, however YAML will be preserved for ease of working with larger rule bases.

You can however do a lot with very little config, using the example configurations and recipes in the documentation.

## Also From Rhizomatics

- [updates2mqtt](https://updates2mqtt.rhizomatics.org.uk) - Automatically update self-hosted Docker containers via Home Assistant's Updates UI, or any other MQTT consumer
- [awesome-mqtt](https://github.com/rhizomatics/awesome-mqtt) -  Curated list of MQTT resources


[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
