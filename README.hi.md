![Supernotify](../assets/images/dark_icon.png){ align=left }

# Supernotify

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)

 <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=rhizomatics&repository=supernotify" target="_blank" rel="noopener noreferrer">
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="HACS में जोड़ें">
   </a>
<br/>
<br/>
<br/>

**Home Assistant के लिए एकीकृत सूचना**

### प्रमुख परिवर्तन v2.0.0

>> SuperNotify का `2.0.0` एक नेटिव Home Assistant UI कॉन्फ़िगरेशन ('ConfigFlow') की ओर बढ़ता है। यदि आपके पास पहले से एक सरल कॉन्फ़िगरेशन है, तो सब कुछ आपके लिए स्वचालित रूप से माइग्रेट कर दिया जाएगा और किसी YAML की आवश्यकता नहीं होगी।

>> यदि आपके पास एक उन्नत कॉन्फ़िगरेशन है (डिलीवरी, परिदृश्य, कैमरा, व्यक्ति, क्रियाएं आदि), तो इन्हें एक नई `supernotify.yaml` फ़ाइल में ले जाने और आपकी `configuration.yaml` में एक `include` कथन जोड़ने के लिए एक *रिपेयर* उठाया जाएगा। या आप चाहें तो `notify` ब्लॉक से कॉन्फ़िगरेशन को अपनी इच्छानुसार मैन्युअल रूप से हटा सकते हैं।

>> दोनों ही स्थितियों में, कुछ भी हटाया या कमेंट आउट नहीं किया जाएगा, इसलिए परिवर्तन को वापस लाना आसान होगा। जब आपको यकीन हो जाए कि नया संस्करण आपके लिए काम कर रहा है, तो पुराना कॉन्फ़िगरेशन हटा दें।

Home Assistant के अंतर्निहित `notify` प्लेटफ़ॉर्म के ऊपर एक **एकीकृत सूचना इंटरफ़ेस**, जो कई सूचना चैनलों और जटिल परिदृश्यों को सरल बनाता है — बहु-चैनल सूचनाएं, सशर्त सूचनाएं, मोबाइल क्रियाएं, कैमरा स्नैपशॉट, ध्वनि संकेत और टेम्पलेट आधारित HTML ईमेल सहित।

Supernotify का एक ही लक्ष्य है — **न्यूनतम संभव सूचना से अधिकतम सूचनाएं भेजना, बिना कोड के और न्यूनतम कॉन्फ़िगरेशन के साथ**।

यह स्वचालन, स्क्रिप्ट और AppDaemon ऐप्स को सरल और रखरखाव योग्य बनाता है। घर में सभी को सूचित करने के लिए केवल एक संदेश वाली सूचना पर्याप्त हो सकती है। ई-मेल पते एक जगह बदलें और Supernotify तय करेगा कि कौन से मोबाइल ऐप्स उपयोग करने हैं।

केवल UI कॉन्फ़िगरेशन के साथ, बिना मोबाइल ऐप नाम कॉन्फ़िगर किए घर में सभी को मोबाइल पुश सूचनाएं भेजना शुरू करें।


## वितरण

Supernotify [Home Assistant Community Shop](https://hacs.xyz) (**HACS**) के माध्यम से उपलब्ध एक कस्टम घटक है। यह [Apache 2.0 लाइसेंस](https://www.apache.org/licenses/LICENSE-2.0) के तहत मुफ्त और ओपन सोर्स है।

## दस्तावेज़ीकरण

[शुरुआत करना](https://supernotify.rhizomatics.org.uk/getting_started/), [मुख्य अवधारणाओं](https://supernotify.rhizomatics.org.uk/concepts/) की व्याख्या और उपलब्ध [ट्रांसपोर्ट अडैप्टर](https://supernotify.rhizomatics.org.uk/transports/) आज़माएं।

बहुत सारे [व्यंजन](https://supernotify.rhizomatics.org.uk/recipes/) उदाहरण कॉन्फ़िगरेशन के साथ उपलब्ध हैं, या [टैग](https://supernotify.rhizomatics.org.uk/tags/) द्वारा ब्राउज़ करें।


## विशेषताएं

* एक क्रिया -> कई सूचनाएं
    * स्वचालन से दोहराव वाली कॉन्फ़िगरेशन और कोड हटाएं
    * अडैप्टर स्वचालित रूप से प्रत्येक एकीकरण के लिए सूचना डेटा को अनुकूलित करते हैं
    * उदाहरण के लिए, ईमेल द्वारा कैमरा स्नैपशॉट के लिए [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) के साथ उपयोग करें
* स्वचालित सेटअप
    * मोबाइल पुश, ईमेल (SMTP) और सूचना इकाइयों के लिए डिलीवरी कॉन्फ़िगरेशन स्वचालित रूप से सेट होती है
    * मोबाइल ऐप्स स्वचालित रूप से खोजे जाते हैं, फोन के निर्माता और मॉडल सहित
    * ध्वनि संकेत के लिए Alexa उपकरण स्वचालित रूप से खोजे जाते हैं
* `notify` एकीकरण से परे
    * ध्वनि संकेत, सायरन, SMS, TTS, Alexa घोषणाएं और ध्वनियां, API कॉल, MQTT उपकरण
    * सभी मानक `notify` और `notify.group` कार्यान्वयन उपलब्ध
    * iPhone जैसे मोबाइल पुश सूचनाओं का सरलीकृत उपयोग
* सशर्त सूचनाएं
    * मानक Home Assistant `conditions` का उपयोग
    * संदेश और प्राथमिकता सहित अतिरिक्त स्थिति चर
    * सूचनाओं को अनुकूलित करने के लिए अधिभोग पहचान के साथ मिलाएं
* **परिदृश्य** सरल और संक्षिप्त कॉन्फ़िगरेशन के लिए
    * सामान्य कॉन्फ़िगरेशन और सशर्त तर्क को पैकेज करें
    * मांग पर (`red_alert`, `nerdy`) या स्थितियों के आधार पर स्वचालित रूप से लागू करें
* एकीकृत व्यक्ति मॉडल
    * एक ईमेल, SMS नंबर या मोबाइल उपकरण परिभाषित करें, फिर सूचना क्रियाओं में `person` इकाई का उपयोग करें
    * लोग स्वचालित रूप से उनके मोबाइल ऐप्स के साथ कॉन्फ़िगर होते हैं
* आसान **HTML ईमेल टेम्पलेट**
    * YAML कॉन्फ़िगरेशन, क्रिया कॉल या स्वतंत्र फ़ाइलों में परिभाषित मानक Jinja2
    * डिफ़ॉल्ट सामान्य टेम्पलेट शामिल
* **मोबाइल क्रियाएं**
    * कई सूचनाओं के लिए मोबाइल क्रियाओं का एक सुसंगत सेट सेट करें
    * मानदंडों के आधार पर मौन करने के लिए *स्नूज़* क्रियाएं शामिल
* लचीले **छवि स्नैपशॉट**
    * कैमरे, MQTT छवियां और छवि URL का समर्थन
    * स्नैपशॉट से पहले और बाद में PTZ प्रीसेट पर कैमरे को पुनः स्थापित करें
* कॉन्फ़िगरेशन स्तर का चयन
    * ट्रांसपोर्ट, डिलीवरी और क्रिया स्तर पर डिफ़ॉल्ट सेट करें
* **डुप्लिकेट सूचना** दमन
    * पुनः अनुमति देने से पहले प्रतीक्षा समय कॉन्फ़िगर करें
* सूचना **संग्रहण** और **डीबग समर्थन**
    * वैकल्पिक रूप से फ़ाइल सिस्टम और/या MQTT विषय पर सूचनाएं संग्रहीत करें
    * पूर्ण डीबग जानकारी शामिल
    * डिलीवरी, ट्रांसपोर्ट, प्राप्तकर्ता और परिदृश्य Home Assistant UI में इकाइयों के रूप में


## उन्नत उपयोग के लिए ही YAML

Supernotify अब बुनियादी सेटअप के लिए मानक Home Assistant UI आधारित कॉन्फ़िगरेशन और उन्नत सुविधाओं के लिए [YAML कॉन्फ़िगरेशन](https://supernotify.rhizomatics.org.uk/configuration/yaml/) का समर्थन करता है। बड़े नियम आधारों के साथ काम करना आसान बनाने के लिए YAML बना रहेगा।

सरल गैर-YAML कॉन्फ़िगरेशन से बहुत कुछ किया जा सकता है, जिसमें मोबाइल पुश सेटअप का स्वचालन भी शामिल है। दस्तावेज़ में [रेसिपी](recipes/index.md) देखें, और यह मोबाइल पुश उदाहरण:

```yaml title="शून्य YAML के साथ, सब कुछ UI से कॉन्फ़िगर"
  - action: supernotify.notify
    data:
        message: नमस्ते! Supernotify परीक्षण — सभी के मोबाइल ऐप्स पर भेज रहे हैं
```


##  Home Assistant के लिए Rhizomatics Open Source

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - भौतिक बटन, उपस्थिति, कैलेंडर और अधिक का उपयोग करके Home Assistant अलार्म नियंत्रण पैनलों को स्वचालित रूप से सक्रिय/निष्क्रिय करें
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - Home Assistant के लिए OpenTelemetry (OTLP) और Syslog ईवेंट कैप्चर


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - फ़ाइल सिस्टम के माध्यम से ANPR/ALPR लाइसेंस प्लेट कैमरों के साथ MQTT में एकीकरण
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Docker इमेज अपडेट पर MQTT के माध्यम से स्वचालित सूचना

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
