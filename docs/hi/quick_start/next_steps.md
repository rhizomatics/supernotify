---
title: आगे क्या करें
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: Supernotify की पहली सूचना के बाद क्या करें - ऑटोमेशन से सूचना भेजें, डैशबोर्ड जोड़ें, चुनें कि किसे और किस बारे में सूचित किया जाए, और रेसिपी में विचार खोजें
---
# आगे क्या करें

शुरुआत एक ऑटोमेशन से करें, क्योंकि सूचनाएँ इसी के लिए होती हैं। बाकी सब वैकल्पिक है और किसी भी क्रम में किया जा सकता है।

## किसी ऑटोमेशन में सूचना जोड़ें { #add-a-notification-to-an-automation }

`supernotify.notify` किसी भी दूसरे एक्शन जैसा ही है, इसलिए यह सामान्य तरीके से ऑटोमेशन में जुड़ता है। यह उदाहरण गलियारे का मोशन सेंसर सक्रिय होने पर एक सूचना भेजता है।

मोशन सेंसर को ट्रिगर बनाकर एक ऑटोमेशन बनाएँ, फिर **एक्शन जोड़ें** चुनें और Supernotify खोजें।

![एक्शन चुनना](../../assets/images/add_action_automation.png){width=600}

संदेश भरें, और [अपनी पहली सूचना](first_notification.md) से जो कुछ भी चाहें, जैसे कोई लक्ष्य या delivery।

![एक्शन कॉन्फ़िगर करना](../../assets/images/automation_action_simple.png){width=600}

```yaml title="मोशन सेंसर ऑटोमेशन"
alias: Hallway motion notification
triggers:
  - trigger: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
actions:
  - action: supernotify.notify
    data:
      title: Motion detected
      message: Something is moving in the hallway
      target: person.john_mcdoe
```

इसे स्पीकर पर भी सुनने के लिए `alexa_devices_announce_all` और `mobile_push` को delivery के रूप में जोड़ें। यह एक्शन और क्या-क्या कर सकता है, यह [सूचनाएँ भेजना](../../usage/notifying.md) में बताया गया है।

बोली गई घोषणाओं और कैमरे की तस्वीर वाला एक विस्तृत उदाहरण [दरवाज़े पर कोई है](../../recipes/someone_at_the_door.md) रेसिपी में देखें।

## डैशबोर्ड जोड़ें { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) में सूचनाओं को नियंत्रित करने और उन पर नज़र रखने, हाथ से भेजने या कॉन्फ़िगरेशन जाँचने के लिए कई विशेष डैशबोर्ड कार्ड हैं।

![ओवरव्यू और transport कार्ड](../../assets/images/cards.png)

[Dashboard](../../configuration/dashboard.md) पेज पर एक पूरा उदाहरण है जिसे नए डैशबोर्ड में पेस्ट किया जा सकता है, और फिर उसे विज़ुअल तरीके से संपादित किया जा सकता है।

## लोगों और delivery को चालू और बंद करें { #switch-people-and-deliveries-on-and-off }

Supernotify जिस भी व्यक्ति को जानता है, उसकी Home Assistant में एक `switch` एंटिटी होती है, और हर delivery की भी। किसी को परेशान होने से बचाने के लिए, या स्पीकर को कुछ देर चुप रखने के लिए, कोई ऑटोमेशन बदले बिना उसे बंद कर दें।

## केवल कुछ डिवाइस को सूचित करें { #notify-just-some-devices }

लक्ष्य कोई व्यक्ति या डिवाइस होने के अलावा कोई **एरिया**, **फ़्लोर** या **लेबल** भी हो सकता है, इसलिए सूचना नीचे की मंज़िल के स्पीकर पर, या रसोई के लेबल वाली हर चीज़ पर जा सकती है। [Targets](../../usage/targets.md) देखें, और सामान्य सवालों के लिए [FAQ](../../faqs.md)।

## सेटिंग्स समायोजित करें { #tune-the-settings }

आर्काइविंग, डुप्लिकेट पहचान और हाउसकीपिंग को **सेटिंग्स → डिवाइस और सेवाएँ** में इंटीग्रेशन के **कॉन्फ़िगर** विकल्प से बदला जा सकता है। [आर्काइविंग](../../configuration/archiving.md) और [डुप्लिकेट पहचान](../../configuration/dupe_detection.md) देखें।

## प्रेरणा लें { #be-inspired }

उदाहरण कॉन्फ़िगरेशन के साथ ढेर सारे विचार [रेसिपी](../../recipes/index.md) में मिलेंगे।

## YAML के साथ और आगे बढ़ें { #go-further-with-yaml }

थोड़े YAML कॉन्फ़िगरेशन से और भी बहुत कुछ संभव है, और यह सब वैकल्पिक है।

- लोगों को ई-मेल पता या फ़ोन नंबर दें, [People](../../configuration/people.md) में
- अपनी खुद की delivery बनाएँ, जैसे HTML ई-मेल या स्पीकरों का एक तय समूह, [Deliveries](../../configuration/deliveries.md) में
- रात में, या जब घर पर कोई न हो, तब सूचनाओं का व्यवहार बदलें, [Scenarios](../../configuration/scenarios.md) के साथ
- कैमरा स्नैपशॉट संलग्न करें, [Multimedia](../../configuration/multimedia.md) में

[उन्नत अवधारणाएँ](advanced_concepts.md) इनके पीछे के विचार समझाती हैं, और [कॉन्फ़िगरेशन](../../configuration/index.md) संदर्भ दस्तावेज़ है।

## मदद पाएँ { #get-help }

[Discussions](https://github.com/rhizomatics/supernotify/discussions) पेज पर पूछें, या किसी AI एजेंट का इस्तेमाल करें - [FAQ](../../faqs.md) का आख़िरी जवाब देखें।
