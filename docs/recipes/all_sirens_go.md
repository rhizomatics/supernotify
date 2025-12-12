---
tags:
  - transport
  - alexa
  - 433mhz
  - critical
  - emergency
  - rest_api
  - chime
  - rflink
  - mqtt
  - siren
  - hikvision
---
# Recipe - All Sirens Go

## Purpose

Notify on a critical issue by having all the sirens in the house make as much noise as possible.

## Implementation

Use a `chime` delivery with a set of aliases that cope with the variety of implementations, and call it in
a notification action, either on its own, or as part of a broader notification with email, mobile push etc

```yaml
    - action: notify.supernotify
      data:
        message: ""
        delivery:
            chimes:
                data:
                    chime_tune: doorbell
```

## Example Configuration

This config assumes that the REST commands, switches, sirens and scripts are set up elsewhere
in Home Assistant.

Note that MQTT based sirens can be easily configured using [MQTT Siren Integration](https://www.home-assistant.io/integrations/siren.mqtt/) so they can be turned on and off like any entity.

```yaml title="Supernotify Config Snippet"
 chime:
      alias: Chimes, sirens, buzzers, doorbells and Alexa noises
      delivery_defaults:
        options:
          chime_aliases:
            red_alert:
                alexa_devices: amzn_sfx_scifi_alarm_04
                siren:
                    tune: emergency
                rest_command:
                    target: rest_command.hikvision_isapi_siren
                    data:
                        alarm_code: 11
                switch:
                    target: switch.rflink_sounder
                script:
                    target: script.ring_all_the_bells
                    data:
                      variables:
                        duration: 25
                        volume: 1.0
```


## Variations

Use a scenario to automatically apply this delivery to any notification sent via Supernotify
with `priority` = `critical`
