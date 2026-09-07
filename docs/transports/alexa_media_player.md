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

The `message_usage` option can be set to `combine_title` or `use_title` to override the default behaviour of speaking the `standard`.

## Voice specific message

Use `spoken_message` in the `data` section of a notification call to provide a different message for a voice notification than used for other transports like email or mobile push.

## Volume management

By default, every announcement assumes background music might be playing on the target device(s) and does the following, all via the Alexa cloud API (`notify.alexa_media`, `media_player.volume_set`, `media_player.media_pause`/`media_stop`/`media_play`):

1. **Snapshot** current volume of every target (falls back to `volume_fallback` if the integration reports `None`, see [AMP issue #1394](https://github.com/alandtse/alexa_media_player/issues/1394)).
2. **Pause** music if playing (or `media_stop` if `pause_music: false`, to suppress the confirmation beep).
3. **Set volume** to the requested `volume`, if any.
4. **Announce** the message.
5. **Wait** for an estimate of the TTS duration (SSML-aware; tune with `tts_char_speed`).
6. **Resume** music playback, if it was paused.
7. **Restore** volume to its prior level.

All of `data` keys below are optional:

| Key | Type | Default | Effect |
| --- | --- | --- | --- |
| `volume` | float 0-1 | none | Desired announcement volume; supports a Jinja2 template. |
| `restore_volume` | bool | `true` | Restore the pre-announcement volume afterwards. |
| `pause_music` | bool | `true` | Pause (rather than stop) music if playing. |
| `volume_fallback` | float 0-1 | `0.5` | Used when a device's current volume can't be read. |
| `wait_for_tts` | bool | `false` | Block delivery until the TTS estimate elapses, even when no volume/music restore is needed — useful to sequence automation steps after the announcement finishes speaking. |
| `tts_char_speed` | float s/ch | `0.06` | Seconds per character for the TTS duration estimate; calibrate per language (see below). |

### Reducing cloud API calls and Notification delay

Each of steps 2, 3, 6 and 7 above is a separate Alexa cloud API call per target device, with parallelism where Home Assistant permits, and step 5's wait only exists to sequence step 6/7 after the announcement. For a pure alert/status announcement where nothing is actually playing music, none of that is needed — it just adds cloud round-trip latency (and can be a real contributor to announcements sounding "late" when there are several target devices, since these calls run per-device).

If this is unnecessary, for example if at least some of the devices are used mainly for announcement purposes and rarely play music, then this can be switched off at the `delivery` or the `delivery_defaults` section of the `transport` configuration:

```yaml
deliveries:
  alexa_all:
    transport: alexa_media_player
    options:
      media_auto_pause: false
```

If this only applies to some Alexa devices, then make two `Delivery` definitions, one for the music players without the `media_auto_pause` override and one with.

### TTS duration calibration

`tts_char_speed` (seconds per character) defaults to `0.06` (Italian/English). Suggested values by language family:

| Language family | s/ch |
| --- | --- |
| Italian / English / French | 0.060 |
| Spanish / Portuguese | 0.058 |
| German | 0.065 |
| Russian / Polish | 0.062 |
| Japanese / Chinese / Korean | 0.180 |
| Arabic | 0.075 |

## References

### Home Assistant Core
- [Alexa Media Player Integration](https://github.com/alandtse/alexa_media_player)
### Other
- [alexapy](https://alexapy.readthedocs.io/en/latest/index.html)
