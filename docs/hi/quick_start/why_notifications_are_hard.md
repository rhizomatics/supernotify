---
title: सूचनाएँ कठिन क्यों हैं
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Home Assistant में एक ही सूचना को ई-मेल, Telegram, मोबाइल पुश और SMS पर एक साथ भेजना कठिन क्यों है, साथ में सूचना एक्शन की अलग-अलग शैलियों की सूची और हर इंटीग्रेशन उन्हें कैसे इस्तेमाल करता है
---
# Home Assistant में सूचनाएँ कठिन क्यों हैं

यह पेज बताता है कि Home Assistant में एक संदेश को कई चैनलों पर भेजना जितना दिखता है उससे कठिन क्यों है। Supernotify
इसी कारण बना है, और यह पेज Home Assistant में सूचनाओं को आसान बनाने के मौजूदा काम में योगदान के रूप में भी लिखा गया
है। यह Home Assistant **2026.11** का वर्णन करता है, जिसे उसके सोर्स कोड से जाँचा गया है। हर रिलीज़ के साथ और इंटीग्रेशन
notify एंटिटी पर आ रहे हैं, इसलिए [तालिका](#integrations-and-their-styles) की कुछ पंक्तियाँ बदलेंगी।

## "मैं बस एक ग्रुप क्यों इस्तेमाल नहीं कर सकता?" { #why-cant-i-just-use-a-group }

मान लीजिए आप चाहते हैं कि एक अलर्ट आपके फ़ोन, आपके ई-मेल, परिवार के एक Telegram चैट और SMS से किसी ऐसे व्यक्ति तक
पहुँचे जिसके पास स्मार्टफ़ोन नहीं है। Home Assistant में notify ग्रुप होते हैं, इसलिए इन चारों का एक ग्रुप बनाकर उसे
भेजना स्वाभाविक लगता है। notify ग्रुप दो तरह के होते हैं, और कोई भी चारों को नहीं रख सकता।

**Notify ग्रुप हेल्पर**, जो UI में बनाया जाता है, **notify एंटिटी** को समूहित करता है और `notify.send_message` से
भेजता है। Companion App, SMTP और Telegram बॉट की notify एंटिटी होती हैं, इसलिए चार में से तीन इसमें आ सकते हैं। SMS
नहीं: Twilio SMS और ClickSend जैसे SMS इंटीग्रेशन में केवल पुरानी शैली का notify एक्शन है। ग्रुप केवल `message` और
`title` भेजता है, और अगर कोई सदस्य title सपोर्ट नहीं करता तो सभी के लिए title हटा देता है। कैमरा स्नैपशॉट, फ़ोन की
सूचना में बटन, HTML ई-मेल बॉडी या कुछ और जोड़ने का कोई तरीका नहीं है।

**पुराना notify ग्रुप**, केवल YAML में, पुराने **notify एक्शन** को समूहित करता है, जैसे
`notify.mobile_app_annas_phone` या `notify.smtp`। Telegram इसमें नहीं आ सकता, क्योंकि उसका notify एक्शन 2026.11 में
हटा दिया गया और केवल notify एंटिटी बची है। बाकी तीन आ सकते हैं, लेकिन हर सदस्य को एक ही कॉल मिलती है:

- `target` का अर्थ हर एक के लिए अलग है: SMTP के लिए ई-मेल पते और Twilio के लिए फ़ोन नंबर, जबकि फ़ोन का अपना एक्शन
  इसे अनदेखा करता है। एक ही `target` सभी के लिए सही नहीं हो सकता।
- `data` हर सदस्य को भेजा जाता है, उसमें जो भी कुंजियाँ हों। एक चित्र Companion App के लिए `data.image`, SMTP के लिए
  `data.images` (स्थानीय फ़ाइलों की सूची) और Twilio SMS के लिए `data.media_url` है। हर सदस्य को अपनी कुंजियों के साथ
  दूसरों के लिए बनी कुंजियाँ भी मिलती हैं।
- हर सदस्य के लिए YAML में स्थिर `data` रखा जा सकता है, लेकिन ऐसा डेटा नहीं जो हर सूचना के साथ बदले, जैसे इस अलर्ट
  का चित्र।

कोई भी ग्रुप यह नहीं जानता कि वह किसे सूचित कर रहा है। फ़ोन बदलने पर ग्रुप को संपादित करना पड़ता है। अगर कोई बाहर है,
या संदेश केवल घर पर मौजूद लोगों को जाना चाहिए, तो ग्रुप यह तय नहीं कर सकता। ग्रुप बस भेजने की जगहों की स्थिर सूचियाँ
हैं।

## ऐसा क्यों है { #why-its-like-this }

इसमें किसी की गलती नहीं है। Home Assistant ने दस वर्षों में सैकड़ों सूचना इंटीग्रेशन जोड़े हैं, हर एक अपनी सेवा की
ज़रूरतों के साथ, और सूचनाओं का साझा हिस्सा हमेशा बहुत छोटा रहा है:

- **केवल `message` साझा है।** `title` अधिकांश एक्शन में है। `target` एक शैली में है और बाकी में नहीं, और हर
  इंटीग्रेशन में उसका अर्थ अलग है। बाकी सब कुछ (चित्र, बटन, प्राथमिकता, ध्वनि, HTML, अटैचमेंट, टैप करने पर होने वाला
  एक्शन) पुरानी शैली में एक मुक्त `data` कुंजी के नीचे जाता है, या नई शैली में इंटीग्रेशन के अपने एक्शन के फ़ील्ड में।
  कोई साझा स्कीमा इन्हें कवर नहीं करता।
- **एक ही विचार के अलग-अलग नाम हैं।** टैप एक्शन iOS पर `data.url` है लेकिन Android पर `data.clickAction`, दोनों
  Companion App में। ntfy में यह `click` है और Prowl व Pushover में `url`। प्राथमिकता Pushover और Prowl में `-2` से `2`,
  ntfy में `1` से `5`, LaMetric में `info`/`warning`/`critical`, और iOS Companion App के लिए `push` के नीचे
  `interruption-level` है।
- **कुछ सेवाओं में हर लक्ष्य का अपना एक्शन है।** Companion App की पुरानी शैली हर फ़ोन के लिए
  `notify.mobile_app_<device>` एक्शन बनाती है, यानी एक्शन का नाम ही लक्ष्य है। ऑटोमेशन व्यक्ति का नहीं, फ़ोन का नाम लेते
  हैं, और फ़ोन बदलने पर उन्हें बदलना पड़ता है।
- **कुछ सेवाओं में एक साथ दो शैलियाँ हैं।** नए इंटीग्रेशन एक notify एंटिटी देते हैं, जो `notify.send_message`, एरिया,
  लेबल और ग्रुप के साथ काम करती है, लेकिन केवल संदेश और title भेजती है। बाकी सब के लिए वे उसी एंटिटी पर लक्षित अपना
  एक्शन जोड़ते हैं, जैसे `smtp.send_message` या `ntfy.publish`। चित्र भेजने के लिए साझा एक्शन छोड़कर इंटीग्रेशन का अपना
  एक्शन इस्तेमाल करना पड़ता है।
- **आवाज़, चाइम और स्क्रीन पर संदेश फिर अलग हैं।** `tts.speak`, `persistent_notification.create`,
  `alexa_devices.send_sound` और `mqtt.publish` हर एक का अपना रूप और अपने लक्ष्य हैं, और इनमें से कोई notify एक्शन नहीं है।

notify एंटिटी सही दिशा हैं: उन्हें एरिया, लेबल और डिवाइस से लक्षित किया जा सकता है, और वे UI में ठीक से दिखती हैं। लेकिन
वे अभी संदेश और title के अलावा कुछ नहीं ले जातीं, और कई इंटीग्रेशन, खासकर SMS वाले, अभी उन पर नहीं आए हैं।

## सूचना एक्शन की शैलियाँ { #the-styles-of-notification-action }

### 1. किसी सेवा के लिए पुराना notify एक्शन { #1-legacy-notify-action-for-a-service }

हर कॉन्फ़िगर की गई सेवा के लिए एक एक्शन, साझा रूप के साथ: `message`, `title`, `target` और मुक्त `data`। `target` का
अर्थ और `data` की कुंजियाँ हर इंटीग्रेशन की अपनी हैं।

```yaml
action: notify.smtp
data:
  title: Front door
  message: The front door has been open for 10 minutes
  target:
    - anna@example.com
  data:
    images:
      - /config/www/snapshots/front_door.jpg
```

Twilio SMS के लिए यही एक्शन `target` के रूप में फ़ोन नंबर और `data` में `media_url` लेता है।

### 2. किसी डिवाइस के लिए पुराना notify एक्शन { #2-legacy-notify-action-for-a-device }

शैली 1 जैसा ही रूप, लेकिन इंटीग्रेशन हर डिवाइस के लिए एक एक्शन बनाता है, इसलिए लक्ष्य एक्शन के नाम में है। मुख्य उदाहरण
Companion App है, हर फ़ोन के लिए `notify.mobile_app_<device>` के साथ, और iOS व Android के लिए अलग `data` कुंजियों के
साथ।

```yaml
action: notify.mobile_app_annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
  data:
    image: /api/camera_proxy/camera.front_door
    url: /lovelace/doors          # iOS
    clickAction: /lovelace/doors  # Android
    actions:
      - action: CLOSE_DOOR
        title: Close it
```

### 3. `notify.send_message` के साथ notify एंटिटी { #3-notify-entity-with-notifysend_message }

सभी notify एंटिटी के लिए एक साझा एक्शन, जिसे एंटिटी, डिवाइस, एरिया या लेबल से लक्षित किया जा सकता है, और जिसे UI
एडिटर पूरी तरह सपोर्ट करता है। यह केवल `message` और `title` लेता है, और title केवल वही एंटिटी इस्तेमाल करती हैं जो इसका
सपोर्ट घोषित करती हैं। कोई `data` नहीं है।

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. इंटीग्रेशन का अपना एक्शन, उसकी notify एंटिटी पर लक्षित { #4-the-integrations-own-action-aimed-at-its-notify-entity }

इंटीग्रेशन की notify एंटिटी लक्ष्य के लिए इस्तेमाल होती है, और इंटीग्रेशन उन सब चीज़ों के लिए सपाट फ़ील्ड वाला अपना
एक्शन जोड़ता है जो `notify.send_message` नहीं भेज सकता। फ़ील्ड हर इंटीग्रेशन में अलग हैं।

```yaml
action: ntfy.publish
target:
  entity_id: notify.ntfy_alerts
data:
  title: Front door
  message: The front door has been open for 10 minutes
  priority: 4
  click: https://my.home/lovelace/doors
  attach: https://my.home/local/snapshots/front_door.jpg
```

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` और
`telegram_bot.send_*` एक्शन इसी तरह काम करते हैं, हर एक अलग फ़ील्ड के साथ।

### 5. इंटीग्रेशन का अपना एक्शन, अपने लक्ष्यों के साथ { #5-the-integrations-own-action-with-its-own-targets }

ऐसे एक्शन जो notify पर बिल्कुल आधारित नहीं हैं और अपना लक्ष्य अपने तरीके से चुनते हैं: एक डिवाइस, एक रूम, एक topic,
या TTS इंजन के साथ एक मीडिया प्लेयर।

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

अन्य हैं `lametric.message` (`device_id` से), `alexa_devices.send_sound` (`device_id` से), `matrix.send_message`
(रूम से), `mqtt.publish` (topic से) और `persistent_notification.create` (कोई लक्ष्य नहीं, यह Home Assistant UI में
दिखता है)।

### 6. ग्रुप { #6-groups }

दोनों तरह के notify ग्रुप [ऊपर](#why-cant-i-just-use-a-group) बताए गए हैं। Notify ग्रुप हेल्पर एक notify एंटिटी है जो
शैली 3 के साथ इस्तेमाल होती है। पुराना notify ग्रुप शैली 1 का एक्शन है जो शैली 1 या 2 के दूसरे एक्शन को कॉल करता है।

## इंटीग्रेशन और उनकी शैलियाँ { #integrations-and-their-styles }

Home Assistant 2026.11। **दोनों** का अर्थ है कि इंटीग्रेशन की दो शैलियाँ हैं, जिनमें notify एंटिटी आसान वाली है और
दूसरी संदेश और title से आगे की हर चीज़ के लिए ज़रूरी है।

| इंटीग्रेशन              | पुराना एक्शन (1 या 2)                     | notify एंटिटी (3)               | अपना एक्शन (4 या 5)                              | संदेश और title से आगे                             |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **दोनों**, हर फ़ोन के लिए        | -                                                | पुराना `data`: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (ई-मेल)            | `notify.<name>`, `target` = पते           | **दोनों**, हर प्राप्तकर्ता के लिए    | `smtp.send_message` (4)                          | पुराना `data.images`, `data.html`; अपना एक्शन `html`, `attachments`, `priority` |
| Telegram बॉट            | 2026.11 में हटाया गया                      | हाँ, हर चैट के लिए                | `telegram_bot.send_message`, `send_photo`, ... (4) | अपने एक्शन: `keyboard`, `inline_keyboard`, `parse_mode`, फ़ोटो और फ़ाइलों के लिए अलग एक्शन |
| Twilio SMS              | `notify.<name>`, `target` = नंबर          | नहीं                            | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = नंबर          | नहीं                            | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = नंबर          | नहीं                            | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = डिवाइस        | नहीं                            | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = चैनल          | नहीं                            | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = चैनल ID      | **दोनों**, हर चैनल के लिए, बिना title | -                                          | पुराना `data.images`, `data.embed`, `data.urls`    |
| Matrix                  | `notify.<name>`, `target` = रूम           | नहीं                            | `matrix.send_message` (5)                        | `data.images`                                     |
| HTML5 पुश               | `notify.<name>`, `target` = रजिस्ट्रेशन     | **दोनों**                        | `html5.send_message` (4)                         | अपना एक्शन: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **दोनों**                        | `ntfy.publish` (4)                               | अपना एक्शन: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, अप्रचलित                  | **दोनों**, बिना title              | `prowl.send_message` (4)                         | अपना एक्शन: `priority`, `url`                      |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **दोनों**                        | `nfandroidtv.send_message` (4)                   | अपना एक्शन: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **दोनों**, बिना title              | `lametric.message` डिवाइस से (5)                 | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | नहीं (प्रस्तावित)                 | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | नहीं                            | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **दोनों**, हर डिवाइस पर बोलना और घोषणा | `alexa_devices.send_sound` डिवाइस से (5) | ध्वनियाँ केवल अपने एक्शन से                         |
| टेक्स्ट-टू-स्पीच          | `notify.<name>` (YAML `platform: tts`)   | नहीं                            | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| स्थायी सूचना              | `notify.persistent_notification`         | नहीं                            | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | हाँ, बिना title                   | `mqtt.publish` topic से (5)                      | कोई भी payload                                    |

## डिवाइस को नहीं, व्यक्ति को सूचित करना { #notifying-a-person-not-a-device }

Home Assistant जानता है कि हर व्यक्ति कौन है और कौन से डिवाइस ट्रैकर उसका पीछा करते हैं, लेकिन यह नहीं कि उस तक कैसे
पहुँचा जाए। Home Assistant टीम इस पर काम कर रही है, समुदाय की "What the Heck?" चर्चा
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879) के बाद,
[आर्किटेक्चर चर्चा #1552](https://github.com/home-assistant/architecture/discussions/1552) में एक प्रस्ताव के साथ: हर
व्यक्ति को उसकी notify एंटिटी की एक सूची मिलती है, और `notify.send_message` को `person.anna` पर भेजा जा सकता है। इससे
रोज़ की सबसे बड़ी समस्या हल होती है, यानी हर ऑटोमेशन में फ़ोन बदलना, और notify एंटिटी किसी तक पहुँचने का स्वाभाविक
तरीका बन जाती हैं।

रिलीज़ होने के बाद Supernotify इसे जितनी जल्दी हो सके सपोर्ट करेगा, व्यक्ति को उसकी जुड़ी notify एंटिटी के ज़रिए भेजकर
भी, और व्यक्ति को भेजे गए `notify.send_message` को Supernotify की अपनी रूटिंग से गुज़रने देकर भी।

## Supernotify इसके लिए क्या करता है { #what-supernotify-does-about-it }

Supernotify एक सूचना को, विकल्पों के एक सेट के साथ, लेता है और उसे हर चैनल के लिए सही कॉल में बदलता है:

- **हर चीज़ के लिए एक एक्शन।** `supernotify.notify` संदेश, title, चित्र, बटन और प्राथमिकता एक बार लेता है, और हर
  [transport](../../transports/index.md) अपने चैनल के सपोर्ट वाली चीज़ों को उस शैली, फ़ील्ड नाम और लक्ष्यों में ढालता
  है जिनकी उसके इंटीग्रेशन को ज़रूरत है, चाहे पुराना एक्शन हो, notify एंटिटी, अपना एक्शन या TTS।
- **लोग, डिवाइस नहीं।** [Recipients](../../configuration/people.md) हर व्यक्ति का ई-मेल, फ़ोन नंबर, Telegram चैट
  आदि रखते हैं, और उनके Companion App वाले फ़ोन अपने आप मिल जाते हैं। `person.anna` को सूचित करें और हर चैनल को सही
  पता मिलता है। हर recipient की अपनी notify एंटिटी भी होती है।
- **किसे मिलना चाहिए।** सूचनाएँ केवल घर पर मौजूद लोगों को, या केवल बाहर गए लोगों को जा सकती हैं, और ज़रूरत पड़ने पर
  दूसरे चैनलों या लोगों पर जा सकती हैं। देखें
  [उपस्थिति के आधार पर रूटिंग, फ़ॉलबैक के साथ](../../recipes/presence_routing_with_fallback.md) रेसिपी।
- **किस बारे में है।** [Scenarios](../../configuration/scenarios.md) और प्राथमिकताएँ तय करती हैं कि कौन से चैनल
  इस्तेमाल हों, ताकि कम प्राथमिकता वाला संदेश केवल फ़ोन पर जाए, जबकि गंभीर संदेश चाइम भी बजाए और स्पीकर पर भी बोला जाए।
- **बहुत बार नहीं।** [स्नूज़](../../usage/snoozing.md) और
  [डुप्लिकेट पहचान](../../configuration/dupe_detection.md) एक ही अलर्ट को बार-बार आने से रोकते हैं।
