---
tags:
  - archiving
  - debugging
  - logging
  - recipe
description: Use a variety of tools within Supernotify and Home Assistant to diagnose why a notification is not acting as intended
---
# Recipe - Debug an Integration

## Purpose

One of the notification integration transports isn't behaving as expected and you want more detailed information.

## Implementation - Logging

Add a module level logging configuration for the specific integration.

## Example Configuration - Logging

In this case the `alexa_devices` transport will start logging at default level by
making this change in HomeAssistant's `configuration.yaml` ( or in an include file if
setup that way)

```yaml
logger:
  custom_components.supernotify.transports.alexa_devices: debug
```

## Implementation - Archiving

Switch on debug mode for archiving, so a `debug_trace` is preserved with each notification.

## Example Configuration - Archiving

```yaml
 notify:
  - name: minimal
    platform: supernotify
    archive:
      file_path: /config/archive/supernotify
      file_retention_days: 3
      debug: true
```

## Implementation - Debug Service Calls

Switch on debug for the delivery, or at transport level for all deliveries.

In debug mode, service calls are made in blocking mode, and a `ServiceResponse`
is captured if the service provides it ( though that is fairly rare for notification
platforms). If the service is failing, raising exceptions etc, this will be visible
in the supernotify logs and in the archived notifications.

By comparison, in normal mode, service calls are sent asynchronously "fire'n'forget"
over an event bus, so any failures would happen in Home Assistant's event handling
workers and wouldn't be visible to Supernotify.


## Example Configuration - Debug Service Calls

In this case all deliveries using the `alexa_devices` transport will call
the Home Assistant service for Alexa in debug mode.

```yaml
transport:
  alexa_devices:
    delivery_defaults:
      debug: true
```

## Example Configuration - Aliases

Most of the config in Supernotify can have an `alias` defined, which can be about anything you like. It is a handy
place to put a reminder of why something is configured oddly, or a nice explanation to show in the UI.

When browsing the exposed entities in Developer Tools, the alias value will show up as a subtitle for each
entity, and may save you puzzling over what you actually meant by that obscure ID months ago.

```yaml
  text_message:
    alias: Mikrotik 4G Router based SMS, the one on the front wall that is only switched on when needed
    transport: sms
    enabled: false
    action: notify.mikrotik_sms
```