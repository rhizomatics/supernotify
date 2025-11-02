# Recipe - Debug an Integration

## Purpose

One of the notification integration methods isn't behaving as expected and you
want more detailed information.

## Implementation

Add a module level logging configuration for the specific integration.

## Example Configuration

In this case the `alexa_devices` method will start logging at default level by
making this change in HomeAssistant's `configuration.yaml` ( or in an include file if
setup that way)

```yaml
logger:
  custom_components.supernotify.methods.alexa_devices: debug
```