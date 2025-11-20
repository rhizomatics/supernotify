---
tags:
  - transport
  - alexa
  - voice_assistant
---
# Alexa Devices Transport

Announce, or speak, a notification using Home Assistant's built-in *Alexa Devices* integration.

The `title_handling` option can be set to `combine_message` or `replace_message` to override the default behaviour of speaking the `message`.

*Note* Home Assistant recommend sending multiple notifications to an [Alexa Device Group](https://www.amazon.co.uk/gp/help/customer/display.html?nodeId=GS8URL9U6PW8SPTA), rather than an explicit list of Alexa devices, to minimize the likelihood of Amazon rate-limiting API calls. Home Assistant managed groups work for announcements, but not speaking, and don't have the API efficiency of Alexa's own groups.

When speaking, [SSML](https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html) is available, for example:

- ```<say-as interpret-as="interjection">bah humbug</say-as>```
- ```<say-as interpret-as='spell-out'>hello</say-as>```
- ```<amazon:emotion name="excited" intensity="high">Activity at front door!</amazon:emotion>```
- ```<amazon:effect name='whispered'>Just a low priority notification</amazon:effect>```
- ```<prosody rate='x-slow'>Saying this slowly</prosody>```
- ```<voice name='Geraint'>hello I'm from Abergavenny</voice>```
- ```<say-as interpret-as='date'>????0922</say-as>``` ( will read as 'September 22nd' )
