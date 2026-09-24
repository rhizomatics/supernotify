---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Kernconcepten van Supernotify voor Home Assistant, waaronder Transport, Delivery, Scenario en Recipient
---
# Kernconcepten

## Hoe alles samenhangt { #how-it-fits-together }

Eén melding vanuit een automatisering kan uitgroeien tot meerdere verschillende meldingen, elk afgestemd op
de manier waarop ze wordt verstuurd.

![Eén melding vanuit een automatisering wordt een e-mail, twee pushmeldingen, een sms en een omroepbericht via een speaker](../assets/images/concepts_flow.svg)

1. **Doelen** - personen worden omgezet in de manieren waarop ze bereikbaar zijn, aan de hand van hun [Recipient](#recipient)-gegevens
2. **Deliveries** - de [Deliveries](#delivery) die van toepassing zijn worden gekozen, standaard of via [Scenario's](#scenario)
3. **Meldingen** - elke delivery pakt de doelen die ze kan gebruiken en verstuurt een passende melding,
   zodat een e-mail een volledige HTML-opmaak met afbeeldingen kan hebben, terwijl de keukenspeaker een kort gesproken bericht krijgt

## Doel (Target) { #target }
- Wie of wat een melding krijgt, en hoe
  - *Directe* doelen
    - e-mailadres
    - telefoonnummer
    - `entity_id` of `device_id`, bijvoorbeeld voor een omroepbericht via een Alexa-apparaat
    - een eigen ID voor een gespecialiseerd transport zoals Telegram
  - *Indirecte* doelen, die in directe doelen kunnen worden omgezet
    - `person_id` om de *Recipient*-functies te gebruiken
    - de standaard doelselectie van Home Assistant, `label_id`, `floor_id` en `area_id`
    - *groeps*doelen (zowel nieuwe als oude Home Assistant-groepen)
- Doelen kunnen een specifieke **Doelcategorie** krijgen, zoals `discord_channel:839439434`; zie [Categorievoorvoegsels](../usage/targets.md#category-prefixes)
- Elk doel wordt uit de lijst opgepakt door de integratie die het het best kan afhandelen
  - Een Notify-entiteit van Alexa Devices wordt bijvoorbeeld afgehandeld door het Alexa Devices-transport, terwijl een algemene Notify-entiteit terugvalt op het minder uitgebreide Notify Entity-transport
- Zie [Targets](../usage/targets.md) voor meer informatie

## Ontvanger (Recipient) { #recipient }
- Een persoon, met optioneel e-mailadres, telefoonnummer, mobiele apparaten of eigen doelen
  - Standaard automatisch gevonden uit de gebruikersaccounts en persoonsentiteiten die al in Home Assistant staan
- Zo is het makkelijker om naar personen te verwijzen in automatiseringen: gebruik `person.joe_mctest` in plaats van in elke melding Joe's e-mailadres te moeten onthouden. Werkt ook voor telefoonnummers als er een geschikte sms-integratie is, of voor eigen ID's zoals Telegram of Discord
- Elke ontvanger heeft ook een Home Assistant-`switch`-entiteit, zodat je iemand makkelijk met rust kunt laten
- Zie [People](../configuration/people.md) en [Recipes](../recipes/index.md) voor meer details

## Transport { #transport }

- Een *transport* is het technische middel om daadwerkelijk te melden, meestal via een van de al geïnstalleerde Home Assistant-integraties
- *Transportadapters* maken het verschil tussen gewone Notify-groepen en Supernotify
  - Een Notify-groep lijkt eenvoudig meldingen via meerdere kanalen mogelijk te maken, maar in de praktijk heeft elk transport andere `data`-structuren (en `data` binnen `data`!), adressering enz., waardoor meldingen uiteindelijk worden teruggebracht tot de kleinste gemene deler, zoals alleen `message`!
- Supernotify heeft standaard adapters voor veelgebruikte transporten zoals e-mail, mobiele push, sms en Alexa, plus een *Generic*-adapter waarmee elke andere Home Assistant-actie kan worden ingepakt
- De transportadapter maakt het mogelijk om één melding naar veel platformen te sturen, ook als die totaal verschillende en onderling onverenigbare interfaces hebben
- Hij past meldingen aan het transport aan: attributen die niet worden geaccepteerd worden weggelaten, `data`-structuren worden omgevormd, alleen de juiste doelen worden gekozen, en waar mogelijk is verdere fijnafstemming mogelijk
- Elk transport heeft een standaardconfiguratie waarmee veel kan worden afgestemd en vooraf ingesteld, zodat je niet in elke melding dezelfde waarden hoeft op te geven
- Zie [Transports](../transports/index.md) voor meer details

## Bezorging (Delivery) { #delivery }

- Een **Delivery** legt elk meldingskanaal vast dat je wilt gebruiken
  - Standaard heeft elk transport een delivery met dezelfde naam, bijvoorbeeld `email` of `mobile_push`
  - Sommige transporten maken automatisch extra deliveries aan, zoals `alexa_devices_announce_all` of `chime_siren_all`
  - Met YAML kun je meer deliveries maken, bijvoorbeeld `html_email` naast de platte-tekst-`email`, of aparte deliveries voor bepaalde spraakassistenten
- Transporten die doelen eenduidig kunnen kiezen, zoals e-mail, mobiele push, sms, Alexa Devices en Notify Entity, worden standaard meegenomen bij het afhandelen van doelen
  - Andere kunnen worden meegenomen via de configuratie, via Scenario's of door erom te vragen in een melding
- Je kunt eigen deliveries maken met een zelfgekozen naam, en meerdere deliveries voor één transport hebben, bijvoorbeeld `plain_email` en `html_email`
- Het [Generic-transport](../transports/generic.md) werkt als *gereedschapskist* om een delivery te maken voor bijna alles wat Home Assistant kan en wat nog niet door een standaardtransport wordt gedekt
- Zie [Deliveries](../configuration/deliveries.md) en [Recipes](../recipes/index.md) voor meer details

## Scenario { #scenario }
- Een pakket instellingen dat op naam kan worden ingeschakeld, of automatisch via Home Assistant-voorwaarden
- Scenario's kunnen handmatig worden gekozen met een `apply_scenarios`-waarde in het `data`-blok van de melding, of automatisch met een standaard Home Assistant-`conditions`-blok
  - Voorwaarden kunnen de tekst van het bericht gebruiken, zodat een Frigate-melding over vogels op het terras anders kan worden afgehandeld dan een insluiper bij een raam
- Gebruik scenario's om meldingen 's nachts minder opdringerig te maken, feestelijker tijdens de feestdagen, of om bepaalde berichten voorrang te geven
- Ze maken het makkelijk om op één plek aanpassingen door te voeren voor veel deliveries of meldingen, en zijn de sleutel tot radicaal eenvoudigere meldingsaanroepen in je automatiseringen
- Zie [Scenarios](../configuration/scenarios.md) en [Recipes](../recipes/index.md) voor meer details

## Prioriteit (Priority) { #priority }
- Een urgentieniveau voor meldingen
   - Er is geen standaardmanier om meldingen te prioriteren, binnen of buiten Home Assistant
   - Supernotify heeft een eigen schema met 5 niveaus, volgens de meest gangbare praktijk, van `minimum` tot `critical`
   - Prioriteit kan worden gebruikt in regels voor scenario's en deliveries, en worden doorgegeven aan meldingsintegraties die het ondersteunen
   - Supernotify heeft een eigen e-mailintegratie, die prioriteit vertaalt naar iets wat Outlook, Apple Mail enz. begrijpen

!!! info
    Voor de technisch geïnteresseerden is er een [Klassendiagram](../developer/class_diagram.md) van de kernklassen bij deze concepten.

# Kernprincipes { #core-principles }

1. Een melding heeft alleen een bericht nodig; al het andere kan een standaardwaarde krijgen, inclusief alle doelen
2. Wat je in een actie-aanroep opgeeft, gaat voor op de standaardwaarden
   - Dit kan worden bijgesteld met opties als `target_usage`
   - Het personenregister wordt alleen gebruikt om doelen te maken als er geen doelen zijn opgegeven
3. Actie > Scenario > Delivery > Transport voor configuratie en standaardwaarden
4. Zo min mogelijk gedoe bij het configureren en aanroepen
   - Doelen kunnen in subcategorieën worden ingedeeld, of één grote lijst zijn van entiteit-ID's, apparaat-ID's, e-mailadressen en telefoonnummers
   - Opties in de actie-`data`, zoals `delivery`, kunnen één waarde, een lijst of een woordenboek zijn

## Ontwikkelaars { #developers }

Zie [Developer Concepts](../developer/concepts.md) voor hoe meldingen door deliveries, doelen en *Envelopes* stromen, en de [Design Principles](../developer/design/principles.md).
