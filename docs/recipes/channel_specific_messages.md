---
tags:
  - recipe
  - delivery
  - transport
title: Channel Specific Messages
description: Tune messages and/or titles for specific deliveries
---
# Recipe - Channel Specific Messages

## Purpose

Tune the notification for a specific channel, for example send shorter messages to SMS.

## Implementation

Use the `delivery` override feature of the notification `data` section to override the message or title. The
delivery name will be matched against the Transport name if there's no matching delivery defined.

## Example Notification

```yaml title="Example Action Call"
- action: supernotify.notify
      data:
        title: "Motion Detection at Back Door"
        message: "Motion has been detected at the back door"
        delivery:
          8tel_sms:
            data:
              message: Back Door Movement
              title: HASS
          mobile_push:
              message: Someone at the back door

```


## Variations

- Use `spoken_message` as a top level `data` attribute to provide an alternative for any Text to Speech announcements, like [Alexa Devices](../transports/alexa_devices.md),[Alexa Media Player](../transports/alexa_media_player.md) or [TTS](../transports/tts.md) for Android.
