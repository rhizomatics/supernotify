---
title: Basisconcepten
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: De paar Supernotify-concepten die je nodig hebt om te beginnen - doelen, recipients, deliveries en prioriteit, en hoe ze samenhangen
---
# Basisconcepten

## Hoe alles samenhangt { #how-it-fits-together }

Eén melding uit een automatisering kan uitgroeien tot meerdere verschillende meldingen, elk afgestemd op de manier waarop die wordt verstuurd.

![Eén melding uit een automatisering wordt een e-mail, twee pushmeldingen, een sms en een aankondiging via een speaker](../../assets/images/concepts_flow.svg)

De afbeelding van links naar rechts gelezen:

1. **Wie er wordt gemeld** - de [doelen](#target). Personen worden omgezet in de manieren waarop ze bereikbaar zijn, aan de hand van hun [recipient](#recipient)-gegevens
2. **Delivery** - de [deliveries](#delivery) die van toepassing zijn worden gekozen, standaard of omdat je erom hebt gevraagd
3. **Meldingen** - elke delivery kiest de doelen die hij kan gebruiken en verstuurt een daarop afgestemde melding, zodat een e-mail een volledige HTML-opmaak met afbeeldingen kan hebben, terwijl de speaker in de keuken een kort gesproken bericht krijgt

Drie woorden dekken bijna alles als je alleen de interface gebruikt.

## Doel (target) { #target }

Een doel is **wie of wat er wordt gemeld**: een persoon, een telefoon, een speaker, een e-mailadres, of een ruimte, verdieping of label dat voor meerdere apparaten staat.

Laat je doelen weg, dan gaat de melding naar iedereen.

## Recipient { #recipient }

Een recipient is **een persoon, zoals Supernotify die kent**: zijn of haar telefoons en tablets, en eventueel een e-mailadres en telefoonnummer. Recipients worden automatisch gevonden via de *Person*-entiteiten in Home Assistant.

Een recipient is geen ander soort doel. Een persoon is een van de dingen die een doel kan zijn, en bij de recipient zoekt Supernotify op hoe die persoon te bereiken is. Daarom werkt `person.joe_mctest` als doel, en heb je het e-mailadres van Joe niet in elke automatisering nodig.

## Delivery { #delivery }

Een delivery is **één manier om een melding te versturen**, met een naam, zoals `mobile_push`, `email` of `alexa_devices_announce_all`. Supernotify maakt deliveries aan voor alles wat het in je Home Assistant vindt, en die zie je in het vak **Delivery** van de actie `supernotify.notify`.

Laat je deliveries weg, dan gebruikt Supernotify de deliveries die zelf kunnen bepalen waarheen ze sturen, zoals mobiele push en e-mail.

## Prioriteit { #priority }

Prioriteit geeft aan **hoe dringend een melding is**, in vijf niveaus: `minimum`, `low`, `medium`, `high` en `critical`. Ze is optioneel, en `medium` als je niets opgeeft. De prioriteit wordt doorgegeven aan telefoons, e-mailprogramma's en alles wat haar begrijpt.

## Nog twee, voor later { #two-more-for-later }

Deze komen overal in de documentatie terug, maar je hebt ze niet nodig om te beginnen.

- Een **transport** is het technische middel achter een delivery, meestal een Home Assistant-integratie zoals de mobiele app, SMTP of Alexa Devices. Een delivery is een transport plus de instellingen die erbij horen, dus één transport kan meerdere deliveries hebben, zoals een gewone `email` en een `html_email`.
- Een **scenario** is een pakket instellingen met een naam, dat verandert welke deliveries worden gebruikt en hoe ze zich gedragen, bijvoorbeeld stiller in de nacht. Scenario's stel je in met YAML.

[Geavanceerde concepten](advanced_concepts.md) behandelt beide, en de rest van wat er met YAML-configuratie kan.
