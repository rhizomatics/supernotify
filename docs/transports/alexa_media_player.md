---
tags:
  - transport
  - alexa
  - voice_assistant
---
# Alexa Media Player Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `alexa_media_player` | :material-github:[`alexa_media_player.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/alexa_media_player.py) | :simple-homeassistantcommunitystore: [Alexa Media Player Integration](https://github.com/alandtse/alexa_media_player) | - |


Announce a message on an Alexa Echo device using the [`alexa_media_player`](https://github.com/alandtse/alexa_media_player) integration available via [HACS](https://www.hacs.xyz).

The `title_handling` option can be set to `combine_message` or `replace_message` to override the default behaviour of speaking the `message`.
