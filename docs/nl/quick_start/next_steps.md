---
title: Wat je daarna kunt doen
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: Wat je kunt doen na een eerste Supernotify-melding - melden vanuit een automatisering, een dashboard toevoegen, kiezen wie en wat wordt gemeld, en ideeën vinden in de recepten
---
# Wat je daarna kunt doen

Begin met een automatisering, want daar zijn meldingen voor. De rest is optioneel en kan in elke volgorde.

## Een melding toevoegen aan een automatisering { #add-a-notification-to-an-automation }

`supernotify.notify` is een actie zoals elke andere, dus je voegt hem op de gebruikelijke manier toe aan een automatisering. Dit voorbeeld verstuurt een melding als een bewegingssensor in de gang afgaat.

Maak een automatisering met de bewegingssensor als trigger, kies dan **Actie toevoegen** en zoek naar Supernotify:

![Actie selecteren](../../assets/images/add_action_automation.png){width=600}

Vul het bericht in, en wat je verder wilt uit [je eerste melding](first_notification.md), zoals een doel of een delivery:

![Actie configureren](../../assets/images/automation_action_simple.png){width=600}

```yaml title="Automatisering met bewegingssensor"
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

Wil je het ook via de speakers horen, voeg dan `alexa_devices_announce_all` en `mobile_push` toe als deliveries. [Meldingen versturen](../../usage/notifying.md) beschrijft wat de actie verder nog kan.

Een uitgebreider voorbeeld, met gesproken aankondigingen en een camerabeeld, staat in het recept [Er staat iemand aan de deur](../../recipes/someone_at_the_door.md).

## Een dashboard toevoegen { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) biedt veel gerichte dashboardkaarten om meldingen te beheren en te volgen, handmatig te versturen of configuraties te testen.

![Overzichts- en transportkaarten](../../assets/images/cards.png)

De pagina [Dashboard](../../configuration/dashboard.md) bevat een volledig voorbeeld om in een nieuw dashboard te plakken, dat je daarna visueel kunt bewerken.

## Personen en deliveries aan- en uitzetten { #switch-people-and-deliveries-on-and-off }

Elke persoon die Supernotify kent heeft een `switch`-entiteit in Home Assistant, en elke delivery ook. Zet er een uit om iemand niet te storen, of om de speakers even stil te houden, zonder automatiseringen aan te passen.

## Alleen bepaalde apparaten melden { #notify-just-some-devices }

Doelen kunnen naast een persoon of apparaat ook een **Ruimte**, **Verdieping** of **Label** zijn, zodat een melding naar de speakers beneden kan gaan, of naar alles met het label voor de keuken. Zie [Targets](../../usage/targets.md) en de [veelgestelde vragen](../../faqs.md).

## De instellingen aanpassen { #tune-the-settings }

Archivering, detectie van duplicaten en opschonen kun je wijzigen via de optie **Configureren** van de integratie, onder **Instellingen → Apparaten & diensten**. Zie [Archivering](../../configuration/archiving.md) en [Detectie van duplicaten](../../configuration/dupe_detection.md).

## Doe inspiratie op { #be-inspired }

In de [recepten](../../recipes/index.md) vind je veel ideeën met voorbeeldconfiguratie.

## Verder gaan met YAML { #go-further-with-yaml }

Met wat YAML-configuratie kan er meer, en alles daarvan is optioneel:

- Personen een e-mailadres of telefoonnummer geven, in [People](../../configuration/people.md)
- Eigen deliveries maken, zoals een HTML-e-mail of een vaste groep speakers, in [Deliveries](../../configuration/deliveries.md)
- Het gedrag van meldingen 's nachts of als er niemand thuis is aanpassen, met [Scenarios](../../configuration/scenarios.md)
- Camerabeelden meesturen, in [Multimedia](../../configuration/multimedia.md)

[Geavanceerde concepten](advanced_concepts.md) legt de ideeën hierachter uit, en [Configuratie](../../configuration/index.md) is het naslagwerk.

## Hulp krijgen { #get-help }

Stel je vraag op de pagina [Discussions](https://github.com/rhizomatics/supernotify/discussions), of gebruik een AI-agent - zie het laatste antwoord in de [veelgestelde vragen](../../faqs.md).
