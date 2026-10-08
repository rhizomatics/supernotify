---
title: Je eerste melding versturen
tags:
  - quickstart
  - developer tools
  - notification
description: Een eerste Supernotify-melding versturen vanuit Home Assistant - naar iedereen, naar één persoon en naar Alexa-speakers
---
# Je eerste melding versturen

Alles op deze pagina doe je in de interface van Home Assistant, direct na de [installatie](installation.md). Elke stap toont ook de YAML, voor wie dat liever gebruikt.

## 1. Iedereen melden { #1-notify-everyone }

Open het [tabblad Acties](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab) in **Ontwikkelhulpmiddelen**, kies de actie `supernotify.notify`, typ een bericht en druk op **Actie uitvoeren**.

![Actie in de ontwikkelhulpmiddelen](../../assets/images/tools_action_notify.png){width=600}

```yaml title="Bericht aan iedereen"
action: supernotify.notify
data:
  message: Something went off in the basement
```

Een melding heeft alleen een bericht nodig. Zonder verdere opgave gaat die naar elke telefoon en tablet met de Home Assistant-app, van iedereen in huis.

## 2. Eén persoon melden { #2-notify-one-person }

Dat zijn waarschijnlijk meer mensen dan je wilt. Kies om het te beperken `person`-entiteiten, of afzonderlijke mobiele apparaten, als **doelen** (targets):

![Alle mobiele apparaten van één persoon melden](../../assets/images/person_notify.png){width=400}

```yaml title="Bericht aan één persoon"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

Nu krijgen alleen de apparaten van John de melding. Door een persoon te kiezen in plaats van een telefoon komt de melding ook nog aan als John een nieuwe telefoon heeft.

## 3. Kiezen hoe er wordt verstuurd { #3-choose-how-its-sent }

Het vak **Delivery** toont de manieren die Supernotify heeft gevonden om meldingen te versturen. Laat je het leeg, dan kiest Supernotify voor je; kies je er zelf uit, dan worden alleen die gebruikt.

![Selectie van de delivery](../../assets/images/delivery_choice.png)

Heb je Alexa-apparaten, gebruik dan `alexa_devices_announce_all` of `alexa_devices_speak_all`. (Announce laat eerst een toon horen, speak niet.) Je kunt ze in één melding combineren met e-mail en meldingen via de mobiele app.

```yaml title="Speakers en telefoons samen"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

Elk krijgt een passende melding: de speakers spreken het bericht uit en de telefoons tonen het.

Werkt dat, dan is de volgende stap [een melding toevoegen aan een automatisering](next_steps.md#add-a-notification-to-an-automation).
