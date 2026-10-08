---
title: इंस्टॉलेशन
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Home Assistant के लिए Supernotify को HACS से इंस्टॉल करें और बिना YAML के UI से सेट अप करें
---

# इंस्टॉलेशन

## HACS से इंस्टॉल करें { #install-from-hacs }

सबसे पहले, पक्का करें कि **HACS** इंस्टॉल है।

अगर नहीं है, तो [HACS के निर्देश](https://hacs.xyz/docs/use/) देखें। Supernotify HACS की डिफ़ॉल्ट रिपॉज़िटरी में से एक है, इसलिए कोई कस्टम रिपॉज़िटरी कॉन्फ़िगर करने की ज़रूरत नहीं है।

Home Assistant के HACS पेज पर, उपलब्ध इंटीग्रेशन की सूची में **Supernotify** चुनें, उसे डाउनलोड करें और Home Assistant को रीस्टार्ट करें।

![HACS में चयन](../../assets/images/hacs_select.png){width=400}

## इंटीग्रेशन जोड़ें { #add-the-integration }

**सेटिंग्स → डिवाइस और सेवाएँ → इंटीग्रेशन जोड़ें** पर जाएँ और **Supernotify** खोजें। डिफ़ॉल्ट मान स्वीकार करें।

![इंटीग्रेशन जोड़ना](../../assets/images/new_integration.png)

## खोज और डिफ़ॉल्ट { #discovery-and-defaults }

सूचनाएँ चालू करने के लिए बस इतना ही करना होता है।

Supernotify देखता है कि Home Assistant में पहले से क्या मौजूद है, और यह सब खोज लेता है।

- **लोग** - Home Assistant में जिनका भी *Person* या *User* है, और वे फ़ोन या टैबलेट जिन पर वे Home Assistant ऐप चलाते हैं
- **सूचना देने के तरीके** - मोबाइल पुश, मौजूदा SMTP ई-मेल इंटीग्रेशन, सभी notify एंटिटी, और Alexa स्पीकर या चाइम जैसे डिवाइस, अगर आपके पास हों

मिले हुए हर तरीके के लिए यह एक *delivery* बनाता है, और अगर आपके पास वैसे डिवाइस हों तो `chime_siren_all` और `alexa_devices_announce_all` जैसी कुछ सुविधाजनक delivery भी।

आर्काइव, डुप्लिकेट पहचान और हाउसकीपिंग की सेटिंग्स बाद में इंटीग्रेशन के **कॉन्फ़िगर** विकल्प से बदली जा सकती हैं।

अब [अपनी पहली सूचना भेजें](first_notification.md)।
