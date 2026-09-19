# Voice

Several voice assistants have specific support, in addition to what can be done for any Home Assistant Notify Entity.

- [Alexa Devices](https://supernotify.rhizomatics.org.uk/transports/alexa_devices/index.md)
- [Alexa Media Player](https://supernotify.rhizomatics.org.uk/transports/alexa_media_player/index.md)
- [TTS](https://supernotify.rhizomatics.org.uk/transports/tts/index.md)

See the transport pages for lots of features and tuning for using these, such as auto-pausing music, using vendor-native groups for faster parallel notifications and more.

## Recipes

Several recipes feature voice notifications:

- [Alexa Backup](https://supernotify.rhizomatics.org.uk/recipes/alexa_alternative_integration/index.md)
- [Alexa Whispers](https://supernotify.rhizomatics.org.uk/recipes/alexa_whisper/index.md)
- [All Sirens Go](https://supernotify.rhizomatics.org.uk/recipes/all_sirens_go/index.md)
- [Seasonal Greetings](https://supernotify.rhizomatics.org.uk/recipes/seasonal_greetings/index.md)
- [Voice Described CCTV](https://supernotify.rhizomatics.org.uk/recipes/voice_described_cctv/index.md)

## Simplifying Text

Voice notifications can sound awful when a device like an Alexa Echo starts reading out web URLs, special symbols or punctuation.

By default, when using a voice aware transport, the notification will be simplified to strip out URLs (where beginning with a scheme like `https:`) and Unicode characters in any of these categories:

- Replace with space
- `_` (underscore)
- Remove Common Symbols
- `(` and `)`
- `$` and `£`
- `<` and `>`
- Remove Unicode Symbols
- `Sc` - Symbol, currency (e.g. €, ¥)
- `So` — Symbol, other (e.g. ✓, ★, emoji, ©, ®)
- `Sk` — Symbol, modifier (e.g. ^, ¨, spacing modifier letters)
- `Sm` — Symbol, math (e.g. +, =, ×, ∑)
- `Mn` — Mark, nonspacing (combining accents/diacritics, e.g. the ́ in é when decomposed)

[SSML](https://en.wikipedia.org/wiki/Speech_Synthesis_Markup_Language) will be left intact for all transports identified as `SPOKEN`, so instructions to whisper, shout or play chimes won't be affected.

This all means that a single notification can be sent for multiple purposes, with more details on mobile push or email and a suitable announcement on voice assistants.

This can be switched on or off for any delivery:

```yaml
delivery:
  apple_push:
    transport: mobile_push
    options:
      simplify_text: false
      strip_urls: true
```

## Overriding Message

If the text simplification isn't enough, you can also craft a specific message for voice assistants.

```yaml
  - action: supernotify.notify
    data:
        message: Somebody has triggered the motion detector at the front porch
        spoken_message: Porch Alert
```

or use the generic delivery overrides

```yaml
  - action: supernotify.notify
    data:
        message: Somebody has triggered the motion detector at the front porch
        delivery:
          mobile_push:
              data:
                message: Someone at the back door
          alexa_devices_announce_all:
              data:
                message: Porch Alert
```

There are also options to combine the title into the message, or drop it out altogether that may work better for you

```yaml
  - action: supernotify.notify
    data:
        title: Home Security
        message: Somebody has triggered the motion detector at the front porch
        # any transport, like a voice assistant, that only looks at `message` will prefix
        # the message with the title. Alternatively, `use_title` uses only the title
        message_usage: combine_title
```

### Noises

While SSML can add a variety of sounds to voice assistants, the best way to use them is with the [Chime](https://supernotify.rhizomatics.org.uk/transports/chime/index.md) transport, which can also be used to unify Alexas making red alert noises with real sirens and doorbell chimes to make as much racket as you need.
