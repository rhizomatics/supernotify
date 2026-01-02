---
tags:
  - transport
  - tts
  - alexa
  - amazon polly
  - text-to-speech
  - voice_assistant
  - android

---
# TTS Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `tts` | :material-github:[`tts.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/tts.py) | :material-home-assistant: [TTS Integration](https://www.home-assistant.io/integrations/tts/) | - |

Announce, or speak, a notification using one of Home Assistant's built-in [*Text-to-Speech* integrations](https://www.home-assistant.io/integrations/#text-to-speech). By default, it uses the `tts.home_assistant_cloud` by Nabu Casa, thougn any supported tts can be used. It also supports the Android Companion App [TTS](https://companion.home-assistant.io/docs/notifications/notifications-basic?_highlight=tts#text-to-speech-notifications)

## Text-to-Speech Integration

This integration automatically sets the action to `tts.speak` and limits the `data` section to the supported values,
such as `cache`, `language` and `options`.

The action can be overridden if desired to the older `tts.say`

The `message_usage` option can be set to `combine_title` or `use_title` to override the default behaviour of speaking the `standard`.

### Choosing the TTS Provider

```yaml
delivery:
  speak_it_out:
    transport: tts
    options:
      - tts_entity_id: tts.google_ai_tts
```

### Changing the Action

```yaml
delivery:
  speak_it_out:
    transport: tts
    action: tts.speak_cloud
    options:
      - tts_entity_id: tts.google_ai_tts
```

### Under the Hood

The Home Assistant [TTS Integration](https://www.home-assistant.io/integrations/tts/) calls
the `tts_entity_id` to generate an audio file from the text, and then uses the `media_player`
virtual integration to play this audio file. The Entity Platform (see [Entity Architecture](https://developers.home-assistant.io/docs/architecture/devices-and-services)) creates jobs per entity for this - not
per platform, so there can be a delay between each device making its announcement. It does however try
to preserve the order in which the `media_player` entities were listed.

## Android Companion App

If a `mobile_app_XXXX` target is passed to this transport, it will check if its an Android ( or more precisely
not an Apple) mobile app, and make a call like:

```yaml title="Android TTS"
action: notify.mobile_app_my_pixel
  data:
    message: "TTS"
    data:
      tts_text: "This is the notification message"
```

Media Player and Android targets can be combined in one call - the `tts` transport will work out which calls to make.

## Alternatives

For Amazon Echo devices, text-to-speech is also available via the [Alexa Devices](./alexa_devices.md) and
[Alexa Media Player](./alexa_media_player.md) transport adaptors.

To get canned sounds rather than speech, use the [Chime](./chime.md) transport adaptor.

## References

### Home Assistant
* [TTS Integration](https://www.home-assistant.io/integrations/tts/)
      * [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20tts%22%20state%3Aopen)
* [TTS Integrations](https://www.home-assistant.io/integrations/#text-to-speech)
    * [Nabu Casa TTS](https://support.nabucasa.com/hc/en-us/articles/25619386304541-Text-to-speech-TTS)
* [Android Companion App TTS](https://companion.home-assistant.io/docs/notifications/notifications-basic?_highlight=tts#text-to-speech-notifications)
