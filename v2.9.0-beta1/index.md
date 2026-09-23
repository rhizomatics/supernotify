This page available in [English](https://supernotify.rhizomatics.org.uk/latest/index.md), [Deutsch](https://supernotify.rhizomatics.org.uk/latest/de/index.md), [Español](https://supernotify.rhizomatics.org.uk/latest/es/index.md), [Français](https://supernotify.rhizomatics.org.uk/latest/fr/index.md), [हिन्दी](https://supernotify.rhizomatics.org.uk/latest/hi/index.md), [Italiano](https://supernotify.rhizomatics.org.uk/latest/it/index.md),[日本語](https://supernotify.rhizomatics.org.uk/latest/ja/index.md), [Nederlands](https://supernotify.rhizomatics.org.uk/latest/nl/index.md), [Polski](https://supernotify.rhizomatics.org.uk/latest/pl/index.md), [Português](https://supernotify.rhizomatics.org.uk/latest/pt/index.md), [中文（简体)](https://supernotify.rhizomatics.org.uk/latest/zh-Hans/index.md)

# Supernotify - Unified Notifications for Home Assistant

**Unified Notification for Home Assistant**

### v2 MAJOR CHANGE - Set up from Home Assistant UI

> > `2.0.0` of SuperNotify moves to a native Home Assistant UI configuration ('ConfigFlow'). If you have an existing simple configuration, everything will be migrated for you and there will be no YAML needed.
> >
> > A *Repair* will be raised to move any advanced configuration (deliveries, scenarios, cameras, persons, actions etc) to a new `supernotify:` section, which can be a `supernotify.yaml` file with an `include` statement to your `configuration.yaml` or however you choose to organize your configuration. Nothing will be deleted or commented out, so remove the old config when you are comfortable the new version is working for you, and this will also clear up warnings from the log about the older notification service.
> >
> > An alternative `supernotify.notify` action is now available that is much easier to configure from automations, and works identically to the existing actions.

A **unified notification interface** on top of HomeAssistant's `notify` platform, to greatly simplify notifying via multiple channels just the way you need it, including conditional notifications, voice announcements, mobile actions, camera snapshots, chimes, template based HTML emails, spooky Hallowe'en announcements and more.

The goal - to make the **simplest possible notification** do as **many notifications as you need** with a **single call**, with **no code**, **minimal configuration** and no need to understand the many quirks of different notification integrations.

**No YAML is required** to get started and easily have [mobile push notifications to all your Home Assistant users](https://supernotify.rhizomatics.org.uk/latest/recipes/simple_mobile_push/index.md), camera snapshots attached to e-mails, [Frigate blueprint notifications sent to email](https://supernotify.rhizomatics.org.uk/latest/recipes/frigate_emails/index.md), add a [Dashboard](https://supernotify.rhizomatics.org.uk/latest/configuration/dashboard/index.md) and cut out duplicate notifications.

Use the [Supernotify Cards](https://github.com/lollox80/supernotify-cards) for elegant [dashboard](https://supernotify.rhizomatics.org.uk/latest/configuration/dashboard/index.md) integration. And with advanced YAML configuration, the possibilities are endless.

Recipes

Get started quickly, or get inspired, with one of the [notification recipes](https://supernotify.rhizomatics.org.uk/latest/recipes/index.md), including: [Make Alexa whisper low priority notifications](https://supernotify.rhizomatics.org.uk/latest/recipes/alexa_whisper/index.md), [Set off sirens for critical alerts](https://supernotify.rhizomatics.org.uk/latest/recipes/all_sirens_go/index.md), [Send HomeAssistant themed HTML e-mail](https://supernotify.rhizomatics.org.uk/latest/recipes/basic_html_email/index.md), [Use the Frigate blueprint to send emails with attached images](https://supernotify.rhizomatics.org.uk/latest/recipes/frigate_emails/index.md), [Move and zoom a camera to take a snapshot](https://supernotify.rhizomatics.org.uk/latest/recipes/move_a_camera_for_snapshot/index.md), [Suppress or escalate notifications based on content](https://supernotify.rhizomatics.org.uk/latest/recipes/content_escalation/index.md) and [Halloween and Christmas themed chimes and voices](https://supernotify.rhizomatics.org.uk/latest/recipes/seasonal_greetings/index.md)

This keeps automations, scripts, AppDaemon apps etc simple and easy to maintain, with all the detail and rules managed all in one place, with lots of support to make even complicated preferences easy to manage. The smallest notification possible - only a message defined - can be enough to trigger everything you need to keep everyone informed. Change e-mail addresses in one place, and let Supernotify handle finding which Mobile Apps to use.

## Distribution

Supernotify is a custom component available via the [Home Assistant Community Shop](https://hacs.xyz) (**HACS**) integration. It's free and open sourced under the [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0).

## Documentation

All you need to get running quickly is at [Getting Started](https://supernotify.rhizomatics.org.uk/getting_started/).

To learn more of what it can do for you, check the [core concepts](https://supernotify.rhizomatics.org.uk/concepts/), and the available [transport adaptors](https://supernotify.rhizomatics.org.uk/transports/). [Notifying](https://supernotify.rhizomatics.org.uk/usage/notifying/) shows how to call Supernotify from automations or the Developer Tools action page.

There are lots of [recipes](https://supernotify.rhizomatics.org.uk/recipes/) with sample config snippets to give you some more ideas, or browse by [tags](https://supernotify.rhizomatics.org.uk/tags/).

Translations for the Home Assistant UI are available for Dutch, English, French, German, Hindi, Italian, Japanese, Polish, Portuguese, Simplified Mandarin and Spanish.

## Features

- One Action -> Multiple Notifications
  - Remove repetitive config and code from automations
  - Adaptors automatically tune notification data for each integration
  - For example, use with a [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) to get camera snapshots by e-mail instead of, or as well as, mobile notifications. See the [Frigate Recipe](https://supernotify.rhizomatics.org.uk/recipes/frigate_emails/) for more info.
- Automated set-up
  - Delivery configuration auto-discovered, including for Alexa Devices, Mobile Push, Email (SMTP).
  - Mobile Apps automatically discovered, including Manufacturer and Model of the phone, which can be used to customize delivery
  - Alexa Devices for sending chime noises automatically discovered from Home Assistant
- Go beyond `notify` integrations
  - Chimes, sirens, SMS, TTS, Alexa Announcements and Sounds, API calls, MQTT devices, Gotify, ntfy, LaMetric, Pushover, Telegram
  - All the standard `notify` and `notify.group` implementations available, including the modern `NotifyEntity` based ones
  - Greatly simplified use of Mobile Push notifications, e.g. for iPhone
  - Standard HomeAssistant behaviour, including data templating and `notify.group`
- Conditional Notifications
  - Using standard Home Assistant `conditions`
  - Extra condition variables added, including message and priority
  - Combine with occupancy detection to easily tune notifications based on who is in, message priority, even the content of the message
- **Scenarios** for simple concise configuration
  - Package up common chunks of config and conditional logic
  - Have them applied on-demand in actions (`red_alert`,`nerdy`) or automatically based on conditions (`everyone_home_day`,`frigate_person`).
  - See the [Alexa Whispering](https://supernotify.rhizomatics.org.uk/recipes/alexa_whisper/), [Home Alone](https://supernotify.rhizomatics.org.uk/recipes/home_alone/) and [Bedtime](https://supernotify.rhizomatics.org.uk/recipes/bedtime/) for simple to use examples.
- Unified Person model
  - Currently missing from Home Assistant.
  - Define an email, SMS number or mobile device, and then use the `person` entity in notification actions, Supernotify works out which attribute to use where
  - People are auto-configured along with their mobile apps based on existing Home Assistant configuration
  - See [People](https://supernotify.rhizomatics.org.uk/configuration/people/) for more info
- Easy **HTML email templates**
  - Standard HomeAssistant Jinja2, defined in YAML config, action calls or as stand-alone files in the `config` director
  - Default general template supplied
- **Dashboard Integration**
  - [Supernotify Cards](https://github.com/lollox80/supernotify-cards) has cards for controlling deliveries, sending out messages, testing configuration and more
- **Mobile Actions**
  - Set up a single set of consistent mobile actions across multiple notifications and reuse across many notifications
  - Include *snoozing* actions to silence based on criteria
- Flexible **Image Snapshots**
  - Supports cameras, MQTT Images and image URLs.
  - Reposition cameras to PTZ presets before and after a snapshot is taken, including special support for Frigate PTZ presets
  - See the [Multimedia](https://supernotify.rhizomatics.org.uk/configuration/multimedia/) documentation for more information.
- **Duplicate Notification** Suppression
  - Tune how long to wait before re-allowing
  - Can be combined with snoozing for specific people or transports
- Notification **Archival** and **Debug Support**
  - Optionally archive notifications to file system and/or MQTT topic
  - Full support for Home Assistant [Context](https://data.home-assistant.io/docs/context/) so notification actions can be traced back to source automations
  - Includes full debug information, including occupancy assumptions, delivery and target selections
  - HomeAssistant Actions ( previously known as services ) to pull back live configuration or last known notification details. See [Actions](https://supernotify.rhizomatics.org.uk/latest/usage/actions/index.md)
  - Deliveries, Transports, Recipients and Scenarios exposed as entities, and can be examined and switched on/off via the Home Assistant UI

## YAML Only for Advanced Use

Presently Supernotify supports standard Home Assistant UI based config for the basic setup, and [YAML configuration](https://supernotify.rhizomatics.org.uk/configuration/yaml/) for advanced features. YAML will be preserved for ease of working with larger rule bases.

A lot can be done with the simple non-YAML configuration, including automation of mobile push setup. See the [recipes](https://supernotify.rhizomatics.org.uk/latest/recipes/index.md) in the documentation, and this mobile push example:

With zero YAML all UI config

```yaml
  - action: supernotify.notify
    data:
        message: Hello! Testing this new Supernotify thing sending to everyone's mobile apps
```

## Known Limitations

- **Links** can be configured but not currently used.
- YAML still required for Transport, Recipient, Action and additional custom Delivery
- Versions of Home Assistant more than 6 major releases ( usually 6 months ) aren't tested against Supernotify
- It is tested against Python 3.13 and Home Assistant 2026.2.3 (the last to support v3.13 only), this will be dropped when Home Assistant 2026.10 is released.

## Rhizomatics Open Source for Home Assistant

### HACS

- [AutoArm](https://autoarm.rhizomatics.org.uk) - Automatically arm and disarm Home Assistant alarm control panels using physical buttons, presence, calendars, sun and more
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - OpenTelemetry (OTLP) and Syslog event capture for Home Assistant

### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integrate with ANPR/ALPR licence plate cameras via file system (NAS/FTP) to MQTT with optional image analysis and UK DVLA integration.
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatically notify via MQTT on Docker image updates, with advanced handling to extract versions and release notes from images, and option to remotely pull and restart containers from Home Assistant. Also available on [PyPI](https://pypi.org/project/updates2mqtt/)
