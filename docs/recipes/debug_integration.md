---
tags:
  - archiving
  - debug
  - logging
  - recipe
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
