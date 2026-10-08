---
title: What to Do Next
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: What to do after a first Supernotify notification - notify from an automation, add a dashboard, choose who and what gets notified, and find ideas in the recipes
---
# What to Do Next

Start with an automation, since that is what notifications are for. The rest are optional, and can be done in any order.

## Add a Notification to an Automation

`supernotify.notify` is an action like any other, so it goes into an automation the usual way. This example sends a notification when a motion sensor in the hallway goes off.

Create an automation, with the motion sensor as the trigger, then choose **Add action** and search for Supernotify:

![Select Action](../assets/images/add_action_automation.png){width=600}

Fill in the message, and anything else you want from [your first notification](first_notification.md), like a target or delivery:

![Configure Action](../assets/images/automation_action_simple.png){width=600}

```yaml title="Motion Sensor Automation"
alias: Hallway motion notification
triggers:
  - trigger: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
actions:
  - action: supernotify.notify
    data:
      title: Motion detected
      message: Something is moving in the hallway
      target: person.john_mcdoe
```

To also hear it on the speakers, add `alexa_devices_announce_all` and `mobile_push` as the deliveries. [Sending Notifications](../usage/notifying.md) covers everything else the action can do.

For a fuller worked example, with spoken announcements and a camera picture, see the [Someone's at the Door](../recipes/someone_at_the_door.md) recipe.

## Add a Dashboard

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) has lots of focused dashboard cards to control and monitor notifications, send out manually, or test configurations.

![Overview and Transport Cards](../assets/images/cards.png)

The [Dashboard](../configuration/dashboard.md) page has a complete example to paste into a new dashboard, which can then be edited visually.

## Switch People and Deliveries On and Off

Each person Supernotify knows about has a Home Assistant `switch` entity, and so does each delivery. Turn one off to stop someone being bothered, or to silence the speakers for a while, without changing any automations.

## Notify Just Some Devices

Targets can be an **Area**, **Floor** or **Label** as well as a person or a device, so a notification can go to the speakers downstairs, or to everything labelled for the kitchen. See [Targets](../usage/targets.md), and the [FAQs](../faqs.md) for common questions.

## Tune the Settings

Archiving, duplicate detection and housekeeping can be changed from the integration's **Configure** option, in **Settings → Devices & Services**. See [Archiving](../configuration/archiving.md) and [Duplicate Detection](../configuration/dupe_detection.md).

## Be Inspired

Find lots of ideas with example configuration in the [Recipes](../recipes/index.md).

## Go Further with YAML

More is possible with some YAML configuration, and all of it is optional:

- Give people an e-mail address or phone number, in [People](../configuration/people.md)
- Create your own deliveries, like an HTML e-mail or a fixed set of speakers, in [Deliveries](../configuration/deliveries.md)
- Change how notifications behave at night, or when nobody is home, with [Scenarios](../configuration/scenarios.md)
- Attach camera snapshots, in [Multimedia](../configuration/multimedia.md)

[Advanced Concepts](advanced_concepts.md) explains the ideas behind these, and [Configuration](../configuration/index.md) is the reference.

## Get Help

Ask at the [Discussions](https://github.com/rhizomatics/supernotify/discussions) page, or use an AI agent - see the last answer in the [FAQs](../faqs.md).
