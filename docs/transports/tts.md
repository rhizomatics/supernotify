---
tags:
  - transport
  - tts
  - alexa
  - amazon polly
  - text-to-speech
  - voice_assistant

---
# TTS Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `tts` | :material-github:[`tts.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/tts.py) | :material-home-assistant: [TTS Integration](https://www.home-assistant.io/integrations/tts/) | - |

Announce, or speak, a notification using one of Home Assistant's built-in [*Text-to-Speech* integrations](https://www.home-assistant.io/integrations/#text-to-speech). By default, it uses the `tts.home_assistant_cloud` by Nabu Casa, thougn any supported tts can be used.

This integration automatically sets the action to `tts.speak` and limits the `data` section to the supported values,
such as `cache`, `language` and `options`.

The action can be overridden if desired to the older `tts.say`

The `message_usage` option can be set to `combine_title` or `use_title` to override the default behaviour of speaking the `standard`.

## Choosing the TTS Provider

```yaml
delivery:
  speak_it_out:
    transport: tts
    options:
      - tts_entity_id: tts.google_ai_tts
```

## Changing the Action

```yaml
delivery:
  speak_it_out:
    transport: tts
    action: tts.speak_cloud
    options:
      - tts_entity_id: tts.google_ai_tts
```

## References

* [Nabu Casa TTS](https://support.nabucasa.com/hc/en-us/articles/25619386304541-Text-to-speech-TTS)
* [Home Assistant TTS Integrations](https://www.home-assistant.io/integrations/#text-to-speech)
* [Home Assistant TTS](https://www.home-assistant.io/integrations/tts/)
