# Alexa Devices Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/alexa_devices/

| Transport ID    | Source                                                                                                                               | Requirements                                                                           | Optional |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | -------- |
| `alexa_devices` | [`alexa_devices.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/alexa_devices.py) | [Alexa Devices Integration](https://www.home-assistant.io/integrations/alexa_devices/) | -        |

Announce, or speak, a notification using Home Assistant's built-in *Alexa Devices* integration.

## Example

Example Notification

```yaml
- action: supernotify.notify
  data:
    message: "Motion detected at the front door"
```

The `message_usage` option can be set to `combine_title` or `use_title` to override the default behaviour of speaking the `standard`.

*Note* Home Assistant recommend sending multiple notifications to an [Alexa Device Group](https://www.amazon.co.uk/gp/help/customer/display.html?nodeId=GS8URL9U6PW8SPTA), rather than an explicit list of Alexa devices, to minimize the likelihood of Amazon rate-limiting API calls. Home Assistant managed groups work for announcements, but not speaking, and don't have the API efficiency of Alexa's own groups.

When speaking, [SSML](https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html) is available, for example:

- `<say-as interpret-as="interjection">bah humbug</say-as>`
- `<say-as interpret-as='spell-out'>hello</say-as>`
- `<amazon:emotion name="excited" intensity="high">Activity at front door!</amazon:emotion>`
- `<amazon:effect name='whispered'>Just a low priority notification</amazon:effect>`
- `<prosody rate='x-slow'>Saying this slowly</prosody>`
- `<voice name='Geraint'>hello I'm from Abergavenny</voice>`
- `<say-as interpret-as='date'>????0922</say-as>` ( will read as 'September 22nd' )

## Voice specific message

Use `spoken_message` in the notification call to provide a different message for a voice notification than used for other transports like email or mobile push.

## Discovery

**Default delivery** If the Alexa Devices integration is configured, has at least one `notify` entity, and no `alexa_devices` delivery is defined, an `alexa_devices` delivery is generated automatically. It has no fixed targets: it's selected whenever a notification targets one of the integration's own `notify` entities, directly or through an area or floor, or a Home Assistant `group`, which is passed on as it is.

**All-device deliveries** Two more deliveries are generated, only used when selected explicitly, for example by `delivery: alexa_devices_announce_all` or a scenario:

| Delivery                     | Targets                                             |
| ---------------------------- | --------------------------------------------------- |
| `alexa_devices_speak_all`    | Every `notify.*_speak` entity of the integration    |
| `alexa_devices_announce_all` | Every `notify.*_announce` entity of the integration |

Each is only generated if there's at least one matching entity. Alexa speaker groups are left out, since their member devices are already included, and would otherwise announce twice.

## References

### Home Assistant Core

- [Alexa Devices Integration](https://www.home-assistant.io/integrations/alexa_devices/)
  - [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20alexa_devices%22%20state%3Aopen)

### Amazon

- [Speech Synthesis Markup Language (SSML) Reference](https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html)
