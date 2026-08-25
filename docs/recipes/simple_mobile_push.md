---
tags:
  - mobile_push
  - ios
  - android
  - apple
  - no_yaml_config
  - recipe
title: Simple Mobile Push Notifications
description: Send mobile push notification to Apple and/or Android Devices
---
# Recipe - Simple Mobile Push Notifications

## Purpose

Send mobile push notifications without any configuration.

## Implementation

All you need is:

1. Install Supernotify from HACS ([Getting Started](../getting_started.md))
  - By default, the configuration will have  *Mobile Device Discovery* and *Person Discovery* switched on
2. If they don't already have it, set up the [Home Assistant Companion App](https://companion.home-assistant.io) for each person/device to be notified
  - This needs a *username* and *password* for each user, see [Adding a Person to Home Assistant](https://www.home-assistant.io/integrations/person/#adding-a-person-to-home-assistant)
  - If the companion app is already installed and connecting to Home Assistant, there's nothing more to do to enable it for Supernotify
3. Add a notification as an *Action* to any Automation

![Select Action](../assets/images/add_action_automation.png){width=400}

![Configure Action](../assets/images/automation_action_simple.png){width=400}

## Variations

See [Mobile Push](../transports/mobile_push.md) for lots more options to add to the notification, such as camera snapshots, sounds, vibrations, links, grouping, priority, badges and more.
