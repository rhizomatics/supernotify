# Recipe - Simple Mobile Push Notifications

## Purpose

Send mobile push notifications without any configuration.

## Implementation

All you need is:

1. Install Supernotify from HACS ([Getting Started](https://supernotify.rhizomatics.org.uk/latest/getting_started/index.md))
   - By default, the configuration will have *Mobile Device Discovery* and *Person Discovery* switched on
1. If they don't already have it, set up the [Home Assistant Companion App](https://companion.home-assistant.io) for each person/device to be notified
   - This needs a *username* and *password* for each user, see [Adding a Person to Home Assistant](https://www.home-assistant.io/integrations/person/#adding-a-person-to-home-assistant)
   - If the companion app is already installed and connecting to Home Assistant, there's nothing more to do to enable it for Supernotify
1. Add a notification as an *Action* to any Automation

## Variations

See [Mobile Push](https://supernotify.rhizomatics.org.uk/latest/transports/mobile_push/index.md) for lots more options to add to the notification, such as camera snapshots, sounds, vibrations, links, grouping, priority, badges and more.
