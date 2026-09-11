---
tags:
  - transport
  - alexa
  - voice_assistant

---
# Alexa Devices Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `alexa_devices` | :material-github:[`alexa_devices.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/alexa_devices.py) | :material-home-assistant: [Alexa Devices Integration](https://www.home-assistant.io/integrations/alexa_devices/) | - |

## Discovery

**Default delivery, unless Alexa Media Player is also available.** If the Alexa Devices
integration is already configured and no `alexa_devices` delivery is defined, an
`alexa_devices` delivery is generated automatically, targeting any matching `notify.*_speak` /
`notify.*_announce` entities present. If the [Alexa Media Player](alexa_media_player.md) HACS
integration is *also* detected, it backs off to explicit-selection only
(`DEFAULT_alexa_devices` is not generated) so the same physical Echo devices aren't
double-notified by both integrations — otherwise it fires on every notification by default.

## Example

```yaml title="Example Notification"
- action: supernotify.notify
  data:
    message: "Motion detected at the front door"
```

Announce, or speak, a notification using Home Assistant's built-in *Alexa Devices* integration.

The `message_usage` option can be set to `combine_title` or `use_title` to override the default behaviour of speaking the `standard`.

*Note* Home Assistant recommend sending multiple notifications to an [Alexa Device Group](https://www.amazon.co.uk/gp/help/customer/display.html?nodeId=GS8URL9U6PW8SPTA), rather than an explicit list of Alexa devices, to minimize the likelihood of Amazon rate-limiting API calls. Home Assistant managed groups work for announcements, but not speaking, and don't have the API efficiency of Alexa's own groups.

When speaking, [SSML](https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html) is available, for example:

- ```<say-as interpret-as="interjection">bah humbug</say-as>```
- ```<say-as interpret-as='spell-out'>hello</say-as>```
- ```<amazon:emotion name="excited" intensity="high">Activity at front door!</amazon:emotion>```
- ```<amazon:effect name='whispered'>Just a low priority notification</amazon:effect>```
- ```<prosody rate='x-slow'>Saying this slowly</prosody>```
- ```<voice name='Geraint'>hello I'm from Abergavenny</voice>```
- ```<say-as interpret-as='date'>????0922</say-as>``` ( will read as 'September 22nd' )

## Voice specific message

Use `spoken_message` in the `data` section of a notification call to provide a different message for a voice
notification than used for other transports like email or mobile push.

## References

### Home Assistant Core
- [Alexa Devices Integration](https://www.home-assistant.io/integrations/alexa_devices/)
    - [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20alexa_devices%22%20state%3Aopen)
### Amazon
- [Speech Synthesis Markup Language (SSML) Reference](https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html)
