# Recipe - Channel Specific Messages

Source: https://supernotify.rhizomatics.org.uk/latest/recipes/channel_specific_messages/

## Purpose

Tune the notification for a specific channel, for example send shorter messages to SMS.

## Implementation

Use the `delivery` override feature of the notification `data` section to override the message or title. The delivery name will be matched against the Transport name if there's no matching delivery defined.

## Example Notification

Example Action Call

```yaml
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
        data:
          message: Someone at the back door
```

## Variations

- Use `spoken_message` as a top level action attribute to provide an alternative for any Text to Speech announcements, like [Alexa Devices](https://supernotify.rhizomatics.org.uk/latest/transports/alexa_devices/index.md),[Alexa Media Player](https://supernotify.rhizomatics.org.uk/latest/transports/alexa_media_player/index.md) or [TTS](https://supernotify.rhizomatics.org.uk/latest/transports/tts/index.md) for Android.
