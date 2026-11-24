---
title: Waarom meldingen lastig zijn
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Waarom het in Home Assistant lastig is om één melding tegelijk via e-mail, Telegram, mobiele push en sms te versturen, met een overzicht van de verschillende stijlen van meldingsacties en hoe elke integratie ze gebruikt
---
# Waarom meldingen lastig zijn in Home Assistant

Deze pagina legt uit waarom één bericht naar meerdere kanalen in Home Assistant lastiger is dan het lijkt. Het is de
reden dat Supernotify bestaat, en de pagina is ook bedoeld als bijdrage aan het huidige werk in Home Assistant om
meldingen eenvoudiger te maken. Ze beschrijft Home Assistant **2026.11**, gecontroleerd aan de hand van de broncode.
Elke release zet meer integraties over naar notify-entiteiten, dus sommige rijen van de
[tabel](#integrations-and-their-styles) zullen veranderen.

## "Waarom kan ik niet gewoon een groep gebruiken?" { #why-cant-i-just-use-a-group }

Stel dat een waarschuwing je telefoon, je e-mail, een Telegram-chat van het gezin en per sms iemand zonder smartphone
moet bereiken. Home Assistant heeft notify-groepen, dus het ligt voor de hand om van die vier een groep te maken en
daarnaar te sturen. Er zijn twee soorten notify-groep, en geen van beide kan alle vier bevatten.

**De helper Notify-groep**, ingesteld in de interface, groepeert **notify-entiteiten** en verstuurt met
`notify.send_message`. De Companion App, SMTP en de Telegram-bot hebben notify-entiteiten, dus drie van de vier
passen erin. Sms niet: de sms-integraties, zoals Twilio SMS en ClickSend, hebben alleen de oudere stijl van
notify-actie. De groep verstuurt alleen `message` en `title`, en laat de titel voor iedereen weg als een lid geen
titels ondersteunt. Er is geen manier om een camerasnapshot, een knop in de melding op de telefoon, een HTML-tekst in
de e-mail of iets anders toe te voegen.

**De oude notify-groep**, alleen in YAML, groepeert de oudere **notify-acties**, zoals
`notify.mobile_app_annas_phone` of `notify.smtp`. Telegram past er niet in, omdat de notify-actie ervan in 2026.11 is
verwijderd en alleen de notify-entiteit over is. De andere drie passen wel, maar elk lid krijgt dezelfde aanroep:

- `target` betekent voor elk iets anders: e-mailadressen voor SMTP en telefoonnummers voor Twilio, terwijl de eigen
  actie van een telefoon het negeert. Eén `target` kan niet voor allemaal kloppen.
- `data` gaat naar elk lid, welke sleutels er ook in staan. Een afbeelding is `data.image` voor de Companion App,
  `data.images` (een lijst met lokale bestanden) voor SMTP en `data.media_url` voor Twilio SMS. Elk lid krijgt naast
  zijn eigen sleutels ook de sleutels die voor de anderen bedoeld zijn.
- Elk lid kan vaste `data` in de YAML hebben, maar geen gegevens die per melding veranderen, zoals een afbeelding voor
  deze waarschuwing.

Geen van beide soorten groep weet wie ze waarschuwt. Als een telefoon wordt vervangen, moet de groep worden aangepast.
Als iemand weg is, of het bericht alleen naar wie thuis is moet gaan, kan de groep dat niet beslissen. Groepen zijn
alleen vaste lijsten van bestemmingen.

## Waarom het zo is { #why-its-like-this }

Dit is niemands schuld. Home Assistant heeft in tien jaar honderden meldingsintegraties gekregen, elk met de behoeften
van een eigen dienst, en het gedeelde deel van meldingen is altijd heel klein geweest:

- **Alleen `message` is gemeenschappelijk.** `title` hebben de meeste acties. `target` bestaat in één stijl en niet
  in de andere, en betekent in elke integratie iets anders. Al het andere (afbeeldingen, knoppen, prioriteit, geluid,
  HTML, bijlagen, acties bij aantikken) staat in de oude stijl onder een vrije `data`-sleutel, of in de nieuwere stijl
  in velden van een eigen actie van de integratie. Geen gedeeld schema dekt ze.
- **Hetzelfde idee heeft verschillende namen.** Een actie bij aantikken is `data.url` op iOS maar `data.clickAction`
  op Android, allebei in de Companion App. Het is `click` in ntfy en `url` in Prowl en Pushover. Prioriteit loopt van
  `-2` tot `2` in Pushover en Prowl, van `1` tot `5` in ntfy, is `info`/`warning`/`critical` in LaMetric, en
  `interruption-level` onder `push` voor de Companion App op iOS.
- **Sommige diensten hebben een actie per bestemming.** De oude stijl van de Companion App maakt een actie
  `notify.mobile_app_<device>` voor elke telefoon, dus de naam van de actie is de bestemming. Automatiseringen noemen
  de telefoon, niet de persoon, en moeten worden aangepast als de telefoon wordt vervangen.
- **Sommige diensten hebben twee stijlen tegelijk.** Nieuwere integraties bieden een notify-entiteit, die werkt met
  `notify.send_message`, ruimtes, labels en groepen, maar alleen bericht en titel verstuurt. Voor al het andere voegen
  ze een eigen actie toe die op dezelfde entiteit gericht is, zoals `smtp.send_message` of `ntfy.publish`. Voor een
  afbeelding moet je de gedeelde actie verlaten en de eigen actie van de integratie gebruiken.
- **Spraak, deurbellen en meldingen op het scherm staan weer apart.** `tts.speak`, `persistent_notification.create`,
  `alexa_devices.send_sound` en `mqtt.publish` hebben elk hun eigen vorm en eigen bestemmingen, en geen ervan is een
  notify-actie.

Notify-entiteiten zijn de goede richting: ze kunnen per ruimte, label en apparaat worden aangesproken en worden goed
getoond in de interface. Ze kunnen echter nog niets anders meenemen dan bericht en titel, en veel integraties, vooral
voor sms, zijn nog niet naar ze overgestapt.

## De stijlen van meldingsacties { #the-styles-of-notification-action }

### 1. Oude notify-actie voor een dienst { #1-legacy-notify-action-for-a-service }

Eén actie voor elke ingestelde dienst, met een gedeelde vorm: `message`, `title`, `target` en een vrije `data`. De
betekenis van `target` en de sleutels in `data` horen bij elke integratie.

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

Dezelfde actie voor Twilio SMS neemt telefoonnummers als `target` en `media_url` in `data`.

### 2. Oude notify-actie voor een apparaat { #2-legacy-notify-action-for-a-device }

Dezelfde vorm als stijl 1, maar de integratie maakt één actie per apparaat, dus de bestemming zit in de naam van de
actie. Het belangrijkste voorbeeld is de Companion App, met `notify.mobile_app_<device>` voor elke telefoon, en
verschillende `data`-sleutels voor iOS en Android.

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

### 3. Notify-entiteit met `notify.send_message` { #3-notify-entity-with-notifysend_message }

Eén gedeelde actie voor alle notify-entiteiten, die per entiteit, apparaat, ruimte of label kan worden aangesproken en
volledig wordt ondersteund in de editor van de interface. Ze neemt alleen `message` en `title`, en de titel wordt
alleen gebruikt door entiteiten die aangeven die te ondersteunen. Er is geen `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. De eigen actie van de integratie, gericht op haar notify-entiteit { #4-the-integrations-own-action-aimed-at-its-notify-entity }

De notify-entiteit van de integratie wordt als bestemming gebruikt, en de integratie voegt een eigen actie toe met
platte velden voor alles wat `notify.send_message` niet kan versturen. De velden verschillen per integratie.

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

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` en de acties
`telegram_bot.send_*` werken op dezelfde manier, elk met andere velden.

### 5. De eigen actie van de integratie, met eigen bestemmingen { #5-the-integrations-own-action-with-its-own-targets }

Acties die helemaal niet op notify gebaseerd zijn en hun bestemming op hun eigen manier kiezen: een apparaat, een
kamer, een topic, of een mediaspeler samen met een TTS-engine.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Andere zijn `lametric.message` (per `device_id`), `alexa_devices.send_sound` (per `device_id`), `matrix.send_message`
(per kamer), `mqtt.publish` (per topic) en `persistent_notification.create` (zonder bestemming, deze verschijnt in de
interface van Home Assistant).

### 6. Groepen { #6-groups }

De twee soorten notify-groep zijn [hierboven](#why-cant-i-just-use-a-group) beschreven. De helper Notify-groep is een
notify-entiteit die met stijl 3 wordt gebruikt. De oude notify-groep is een actie van stijl 1 die andere acties van
stijl 1 of 2 aanroept.

## Integraties en hun stijlen { #integrations-and-their-styles }

Home Assistant 2026.11. **Beide** betekent dat de integratie twee stijlen heeft, waarbij de notify-entiteit de
makkelijke is en de andere nodig is voor alles naast bericht en titel.

| Integratie              | Oude actie (1 of 2)                      | Notify-entiteit (3)            | Eigen actie (4 of 5)                             | Meer dan bericht en titel                         |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Beide**, per telefoon        | -                                                | Oude `data`: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (e-mail)           | `notify.<name>`, `target` = adressen     | **Beide**, per ontvanger       | `smtp.send_message` (4)                          | Oud `data.images`, `data.html`; eigen actie `html`, `attachments`, `priority` |
| Telegram-bot            | Verwijderd in 2026.11                    | Ja, per chat                   | `telegram_bot.send_message`, `send_photo`, ... (4) | Eigen acties: `keyboard`, `inline_keyboard`, `parse_mode`, aparte acties voor foto's en bestanden |
| Twilio SMS              | `notify.<name>`, `target` = nummers      | Nee                            | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = nummers      | Nee                            | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = nummers      | Nee                            | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = apparaten    | Nee                            | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = kanalen      | Nee                            | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = kanaal-ID's | **Beide**, per kanaal, zonder titel | -                                           | Oud `data.images`, `data.embed`, `data.urls`      |
| Matrix                  | `notify.<name>`, `target` = kamers       | Nee                            | `matrix.send_message` (5)                        | `data.images`                                     |
| HTML5-push              | `notify.<name>`, `target` = registraties | **Beide**                      | `html5.send_message` (4)                         | Eigen actie: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Beide**                      | `ntfy.publish` (4)                               | Eigen actie: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, verouderd               | **Beide**, zonder titel        | `prowl.send_message` (4)                         | Eigen actie: `priority`, `url`                    |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Beide**                      | `nfandroidtv.send_message` (4)                   | Eigen actie: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Beide**, zonder titel        | `lametric.message` per apparaat (5)              | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | Nee (voorgesteld)              | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | Nee                            | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Beide**, spreken en aankondigen per apparaat | `alexa_devices.send_sound` per apparaat (5) | Geluiden alleen via de eigen actie   |
| Tekst-naar-spraak       | `notify.<name>` (YAML `platform: tts`)   | Nee                            | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Blijvende melding       | `notify.persistent_notification`         | Nee                            | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Ja, zonder titel               | `mqtt.publish` per topic (5)                     | Elke payload                                      |

## Een persoon waarschuwen, niet een apparaat { #notifying-a-person-not-a-device }

Home Assistant weet wie elke persoon is en welke apparaattrackers die persoon volgen, maar niet hoe die te bereiken
is. Het Home Assistant-team werkt hieraan, na de communitydiscussie "What the Heck?"
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), met een
voorstel in [architectuurdiscussie #1552](https://github.com/home-assistant/architecture/discussions/1552): elke
persoon krijgt een lijst van zijn notify-entiteiten, en `notify.send_message` kan naar `person.anna` worden gestuurd.
Dat lost het grootste dagelijkse probleem op, de telefoon in elke automatisering moeten vervangen, en maakt
notify-entiteiten de natuurlijke manier om iemand te bereiken.

Supernotify zal dit zo snel mogelijk ondersteunen zodra het is uitgebracht, zowel door naar een persoon te sturen via
diens gekoppelde notify-entiteiten als door `notify.send_message` naar een persoon via de eigen routering van
Supernotify te laten gaan.

## Wat Supernotify eraan doet { #what-supernotify-does-about-it }

Supernotify neemt één melding, met één set opties, en maakt daar voor elk kanaal de juiste aanroep van:

- **Eén actie voor alles.** `supernotify.notify` neemt bericht, titel, afbeeldingen, knoppen en prioriteit één keer,
  en elke [transport](../../transports/index.md) zet wat zijn kanaal ondersteunt om naar de stijl, veldnamen en
  bestemmingen die zijn integratie nodig heeft, of dat nu een oude actie, notify-entiteit, eigen actie of TTS is.
- **Personen, geen apparaten.** [Recipients](../../configuration/people.md) bevatten de e-mail, het telefoonnummer,
  de Telegram-chat enzovoort van elke persoon, en hun telefoons met de Companion App worden automatisch gevonden.
  Waarschuw `person.anna` en elk kanaal krijgt het juiste adres. Elke recipient krijgt ook een eigen notify-entiteit.
- **Wie het moet krijgen.** Meldingen kunnen alleen naar wie thuis is gaan, of alleen naar wie weg is, en uitwijken
  naar andere kanalen of personen. Zie het recept
  [Routering op aanwezigheid met terugval](../../recipes/presence_routing_with_fallback.md).
- **Waar het over gaat.** [Scenarios](../../configuration/scenarios.md) en prioriteiten bepalen welke kanalen worden
  gebruikt, zodat een bericht met lage prioriteit alleen naar de telefoon gaat, terwijl een kritiek bericht ook de
  deurbellen laat klinken en via de luidsprekers wordt uitgesproken.
- **Niet te vaak.** [Snoozen](../../usage/snoozing.md) en
  [duplicaatdetectie](../../configuration/dupe_detection.md) voorkomen dat dezelfde waarschuwing zich herhaalt.
