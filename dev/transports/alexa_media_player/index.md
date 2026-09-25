# Alexa Media Player Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/alexa_media_player/

| Transport ID         | Source                                                                                                                                         | Requirements                                                                     | Optional |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | -------- |
| `alexa_media_player` | [`alexa_media_player.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/alexa_media_player.py) | [Alexa Media Player Integration](https://github.com/alandtse/alexa_media_player) | -        |

## Discovery

**Delivery (explicit selection).** If the `alexa_media` HACS integration's `notify.alexa_media*` service is registered and no `alexa_media_player` delivery is defined, an `alexa_media_player` delivery is generated automatically — but since a target has no automatic mapping to a recipient or entity, it only fires when selected explicitly (`data: {data: {delivery: [alexa_media_player]}}` or a scenario), not by default.

## Example

Example Notification

```yaml
- action: supernotify.notify
  data:
    message: "Motion detected at the front door"
    delivery:
        alexa_media_player:
            target:
                - media_player.kitchen_echo
```

Announce a message on an Alexa Echo device using the [`alexa_media_player`](https://github.com/alandtse/alexa_media_player) integration available via [HACS](https://www.hacs.xyz).

The `message_usage` option can be set to `combine_title` or `use_title` to override the default behaviour of speaking the `standard`.

## Voice specific message

Use `spoken_message` in the notification call to provide a different message for a voice notification than used for other transports like email or mobile push.

## Volume management

By default, every announcement assumes background music might be playing on the target device(s) and does the following, all via the Alexa cloud API (`notify.alexa_media`, `media_player.volume_set`, `media_player.media_pause`/`media_stop`/`media_play`):

1. **Snapshot** current volume of every target (falls back to `volume_fallback` if the integration reports `None`, see [AMP issue #1394](https://github.com/alandtse/alexa_media_player/issues/1394)).
1. **Pause** music if playing (or `media_stop` if `pause_music: false`, to suppress the confirmation beep).
1. **Set volume** to the requested `volume`, if any.
1. **Announce** the message.
1. **Wait** for an estimate of the TTS duration (SSML-aware; tune with `tts_char_speed`).
1. **Resume** music playback, if it was paused.
1. **Restore** volume to its prior level.

All of `data` keys below are optional:

| Key               | Type       | Default | Effect                                                                                                                                                                     |
| ----------------- | ---------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `volume`          | float 0-1  | none    | Desired announcement volume; supports a Jinja2 template.                                                                                                                   |
| `restore_volume`  | bool       | `true`  | Restore the pre-announcement volume afterwards.                                                                                                                            |
| `pause_music`     | bool       | `true`  | Pause (rather than stop) music if playing.                                                                                                                                 |
| `volume_fallback` | float 0-1  | `0.5`   | Used when a device's current volume can't be read.                                                                                                                         |
| `wait_for_tts`    | bool       | `false` | Block delivery until the TTS estimate elapses, even when no volume/music restore is needed — useful to sequence automation steps after the announcement finishes speaking. |
| `audio_url`       | str        | -       | Play an audio file before the message, see [Playing an audio file](#playing-an-audio-file).                                                                                |
| `audio_duration`  | float s    | `0`     | Length of the `audio_url` clip, added to the TTS wait before restoring volume or resuming music.                                                                           |
| `tts_char_speed`  | float s/ch | `0.06`  | Seconds per character for the TTS duration estimate; calibrate per language (see below).                                                                                   |

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

| Language family             | s/ch  |
| --------------------------- | ----- |
| Italian / English / French  | 0.060 |
| Spanish / Portuguese        | 0.058 |
| German                      | 0.065 |
| Russian / Polish            | 0.062 |
| Japanese / Chinese / Korean | 0.180 |
| Arabic                      | 0.075 |

## Playing an audio file

Echo devices can't play an arbitrary mp3 via `media_player.play_media`, but Alexa will play one inside an SSML `<audio>` tag. Set `audio_url` in the delivery `data` and the transport builds the SSML for you:

Example Notification

```yaml
- action: supernotify.notify
  data:
    message: "Someone at the front door"
    delivery:
      alexa_media_player:
        data:
          audio_url: /local/sounds/doorbell.mp3
          volume: 0.4
```

- The clip plays first, then the message is spoken. Set `message: ""` in the delivery `data` for the sound only
- A relative URL is made absolute with the Home Assistant external URL
- `type` is always `tts` when `audio_url` is set, overriding any `type: announce` in the delivery config, since Alexa plays nothing for SSML audio in announce mode
- The message is treated as plain text and escaped, so don't combine `audio_url` with your own SSML in the message
- For clips longer than a few seconds, set `audio_duration` (seconds) so that volume restore and music resume wait for the clip to finish

Amazon's servers, not the Echo, fetch the file, so it has strict requirements:

- Public `https` URL with a valid, trusted certificate, e.g. via Nabu Casa or a Let's Encrypt domain. A LAN address or a self-signed certificate won't play
- MP3, 48 kbps, sample rate 16000, 22050 or 24000 Hz, at most 240 seconds

Convert an existing file with:

```bash
ffmpeg -i original.mp3 -ac 2 -codec:a libmp3lame -b:a 48k -ar 24000 doorbell.mp3
```

## References

### Home Assistant Core

- [Alexa Media Player Integration](https://github.com/alandtse/alexa_media_player)

### Other

- [alexapy](https://alexapy.readthedocs.io/en/latest/index.html)
