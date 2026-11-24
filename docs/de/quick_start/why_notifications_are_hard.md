---
title: Warum Benachrichtigungen schwierig sind
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Warum es in Home Assistant schwierig ist, eine Benachrichtigung zugleich per E-Mail, Telegram, Mobile Push und SMS zu senden, mit einem Katalog der verschiedenen Arten von Benachrichtigungsaktionen und wie jede Integration sie nutzt
---
# Warum Benachrichtigungen in Home Assistant schwierig sind

Diese Seite erklärt, warum eine Nachricht an mehrere Kanäle in Home Assistant schwieriger ist, als es aussieht. Das
ist der Grund, warum es Supernotify gibt, und die Seite ist zugleich als Beitrag zur aktuellen Arbeit in
Home Assistant gedacht, Benachrichtigungen einfacher zu machen. Sie beschreibt Home Assistant **2026.11**, geprüft am
Quellcode. Mit jeder Version wechseln mehr Integrationen zu Notify-Entitäten, daher werden sich einige Zeilen der
[Tabelle](#integrations-and-their-styles) ändern.

## „Warum kann ich nicht einfach eine Gruppe verwenden?" { #why-cant-i-just-use-a-group }

Angenommen, eine Meldung soll Ihr Telefon, Ihre E-Mail, einen Familien-Chat in Telegram und per SMS jemanden ohne
Smartphone erreichen. Home Assistant hat Notify-Gruppen, also liegt es nahe, eine Gruppe aus diesen vier zu bilden und
an sie zu senden. Es gibt zwei Arten von Notify-Gruppen, und keine kann alle vier aufnehmen.

**Der Notify-Gruppen-Helfer**, in der Oberfläche eingerichtet, fasst **Notify-Entitäten** zusammen und sendet mit
`notify.send_message`. Die Companion App, SMTP und der Telegram-Bot haben Notify-Entitäten, also passen drei der vier
hinein. SMS nicht: Die SMS-Integrationen wie Twilio SMS und ClickSend haben nur die ältere Art von Notify-Aktion. Die
Gruppe sendet nur `message` und `title`, und sie lässt den Titel für alle weg, wenn ein Mitglied keine Titel
unterstützt. Es gibt keine Möglichkeit, einen Kamera-Schnappschuss, eine Schaltfläche in der Benachrichtigung auf dem
Telefon, einen HTML-E-Mail-Text oder sonst etwas hinzuzufügen.

**Die alte Notify-Gruppe**, nur per YAML, fasst die älteren **Notify-Aktionen** zusammen, etwa
`notify.mobile_app_annas_phone` oder `notify.smtp`. Telegram passt nicht hinein, weil seine Notify-Aktion in 2026.11
entfernt wurde und nur die Notify-Entität übrig ist. Die anderen drei passen, aber jedes Mitglied bekommt denselben
Aufruf:

- `target` bedeutet für jedes etwas anderes: E-Mail-Adressen für SMTP und Telefonnummern für Twilio, während die
  eigene Aktion eines Telefons es ignoriert. Ein einziges `target` kann nicht für alle stimmen.
- `data` geht an jedes Mitglied, ganz gleich, welche Schlüssel es enthält. Ein Bild ist `data.image` für die
  Companion App, `data.images` (eine Liste lokaler Dateien) für SMTP und `data.media_url` für Twilio SMS. Jedes
  Mitglied bekommt neben seinen eigenen auch die Schlüssel, die für die anderen gedacht sind.
- Jedes Mitglied kann feste `data` im YAML haben, aber keine Daten, die sich pro Benachrichtigung ändern, etwa ein
  Bild für genau diese Meldung.

Keine der beiden Gruppenarten weiß, wen sie benachrichtigt. Wird ein Telefon ersetzt, muss die Gruppe bearbeitet
werden. Ist jemand unterwegs, oder soll die Nachricht nur an diejenigen gehen, die zu Hause sind, kann die Gruppe das
nicht entscheiden. Gruppen sind nur feste Listen von Zielen.

## Warum das so ist { #why-its-like-this }

Das ist niemandes Fehler. Home Assistant hat in zehn Jahren Hunderte von Benachrichtigungs-Integrationen
hinzugewonnen, jede mit den Anforderungen ihres eigenen Dienstes, und der gemeinsame Teil von Benachrichtigungen war
immer sehr klein:

- **Nur `message` ist allen gemeinsam.** `title` haben die meisten Aktionen. `target` gibt es in einer Art und in
  den anderen nicht, und es bedeutet in jeder Integration etwas anderes. Alles Weitere (Bilder, Schaltflächen,
  Priorität, Ton, HTML, Anhänge, Aktionen beim Antippen) steht bei der alten Art unter einem frei formbaren
  `data`-Schlüssel, oder bei der neueren Art in Feldern einer eigenen Aktion der Integration. Kein gemeinsames Schema
  deckt sie ab.
- **Dieselbe Idee hat verschiedene Namen.** Eine Aktion beim Antippen ist `data.url` unter iOS, aber
  `data.clickAction` unter Android, beides in der Companion App. In ntfy heißt sie `click`, in Prowl und Pushover
  `url`. Die Priorität reicht in Pushover und Prowl von `-2` bis `2`, in ntfy von `1` bis `5`, in LaMetric ist sie
  `info`/`warning`/`critical`, und für die Companion App unter iOS ist es `interruption-level` unter `push`.
- **Manche Dienste haben eine Aktion pro Ziel.** Die alte Art der Companion App erzeugt eine Aktion
  `notify.mobile_app_<device>` für jedes Telefon, der Aktionsname ist also das Ziel. Automatisierungen nennen das
  Telefon, nicht die Person, und müssen geändert werden, wenn das Telefon ersetzt wird.
- **Manche Dienste haben zwei Arten zugleich.** Neuere Integrationen bieten eine Notify-Entität, die mit
  `notify.send_message`, Bereichen, Labels und Gruppen funktioniert, aber nur Nachricht und Titel sendet. Für alles
  andere fügen sie eine eigene Aktion hinzu, die auf dieselbe Entität zielt, etwa `smtp.send_message` oder
  `ntfy.publish`. Für ein Bild muss man die gemeinsame Aktion verlassen und die eigene Aktion der Integration nehmen.
- **Sprache, Gongs und Bildschirmmeldungen sind wieder etwas anderes.** `tts.speak`,
  `persistent_notification.create`, `alexa_devices.send_sound` und `mqtt.publish` haben jeweils ihre eigene Form und
  eigene Ziele, und keine davon ist eine Notify-Aktion.

Notify-Entitäten sind die richtige Richtung: Sie lassen sich nach Bereich, Label und Gerät ansprechen und erscheinen
richtig in der Oberfläche. Sie können aber noch nichts außer Nachricht und Titel übertragen, und viele Integrationen,
vor allem SMS, sind noch nicht zu ihnen gewechselt.

## Die Arten von Benachrichtigungsaktionen { #the-styles-of-notification-action }

### 1. Alte Notify-Aktion für einen Dienst { #1-legacy-notify-action-for-a-service }

Eine Aktion für jeden eingerichteten Dienst, mit gemeinsamer Form: `message`, `title`, `target` und frei formbares
`data`. Die Bedeutung von `target` und die Schlüssel in `data` gehören zur jeweiligen Integration.

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

Dieselbe Aktion für Twilio SMS nimmt Telefonnummern als `target` und `media_url` in `data`.

### 2. Alte Notify-Aktion für ein Gerät { #2-legacy-notify-action-for-a-device }

Dieselbe Form wie Art 1, aber die Integration erzeugt eine Aktion pro Gerät, das Ziel steckt also im Aktionsnamen.
Das wichtigste Beispiel ist die Companion App mit `notify.mobile_app_<device>` für jedes Telefon und mit
unterschiedlichen `data`-Schlüsseln für iOS und Android.

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

### 3. Notify-Entität mit `notify.send_message` { #3-notify-entity-with-notifysend_message }

Eine gemeinsame Aktion für alle Notify-Entitäten, die nach Entität, Gerät, Bereich oder Label angesprochen werden kann
und im Editor der Oberfläche voll unterstützt wird. Sie nimmt nur `message` und `title`, und der Titel wird nur von
Entitäten verwendet, die ihn unterstützen. Es gibt kein `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. Die eigene Aktion der Integration, auf ihre Notify-Entität gerichtet { #4-the-integrations-own-action-aimed-at-its-notify-entity }

Als Ziel dient die Notify-Entität der Integration, und die Integration fügt eine eigene Aktion mit flachen Feldern
für alles hinzu, was `notify.send_message` nicht senden kann. Die Felder unterscheiden sich je nach Integration.

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

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` und die Aktionen
`telegram_bot.send_*` funktionieren genauso, jeweils mit anderen Feldern.

### 5. Die eigene Aktion der Integration, mit eigenen Zielen { #5-the-integrations-own-action-with-its-own-targets }

Aktionen, die gar nicht auf Notify beruhen und ihr Ziel auf eigene Weise wählen: ein Gerät, einen Raum, ein Topic
oder einen Mediaplayer zusammen mit einer TTS-Engine.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Weitere sind `lametric.message` (per `device_id`), `alexa_devices.send_sound` (per `device_id`),
`matrix.send_message` (per Raum), `mqtt.publish` (per Topic) und `persistent_notification.create` (ohne Ziel, sie
erscheint in der Oberfläche von Home Assistant).

### 6. Gruppen { #6-groups }

Die beiden Arten von Notify-Gruppen sind [oben](#why-cant-i-just-use-a-group) beschrieben. Der Notify-Gruppen-Helfer
ist eine Notify-Entität, die mit Art 3 verwendet wird. Die alte Notify-Gruppe ist eine Aktion der Art 1, die andere
Aktionen der Art 1 oder 2 aufruft.

## Integrationen und ihre Arten { #integrations-and-their-styles }

Home Assistant 2026.11. **Beide** heißt, dass die Integration zwei Arten hat, wobei die Notify-Entität die einfache ist
und die andere für alles über Nachricht und Titel hinaus nötig ist.

| Integration             | Alte Aktion (1 oder 2)                   | Notify-Entität (3)             | Eigene Aktion (4 oder 5)                         | Über Nachricht und Titel hinaus                   |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Beide**, pro Telefon         | -                                                | Alte `data`: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (E-Mail)           | `notify.<name>`, `target` = Adressen     | **Beide**, pro Empfänger       | `smtp.send_message` (4)                          | Alt `data.images`, `data.html`; eigene Aktion `html`, `attachments`, `priority` |
| Telegram-Bot            | In 2026.11 entfernt                      | Ja, pro Chat                   | `telegram_bot.send_message`, `send_photo`, ... (4) | Eigene Aktionen: `keyboard`, `inline_keyboard`, `parse_mode`, eigene Aktionen für Fotos und Dateien |
| Twilio SMS              | `notify.<name>`, `target` = Nummern      | Nein                           | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = Nummern      | Nein                           | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = Nummern      | Nein                           | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = Geräte       | Nein                           | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = Kanäle       | Nein                           | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = Kanal-IDs   | **Beide**, pro Kanal, ohne Titel | -                                              | Alt `data.images`, `data.embed`, `data.urls`      |
| Matrix                  | `notify.<name>`, `target` = Räume        | Nein                           | `matrix.send_message` (5)                        | `data.images`                                     |
| HTML5 Push              | `notify.<name>`, `target` = Registrierungen | **Beide**                   | `html5.send_message` (4)                         | Eigene Aktion: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Beide**                      | `ntfy.publish` (4)                               | Eigene Aktion: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, veraltet                | **Beide**, ohne Titel          | `prowl.send_message` (4)                         | Eigene Aktion: `priority`, `url`                  |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Beide**                      | `nfandroidtv.send_message` (4)                   | Eigene Aktion: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Beide**, ohne Titel          | `lametric.message` per Gerät (5)                 | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | Nein (vorgeschlagen)           | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | Nein                           | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Beide**, Sprechen und Ankündigen pro Gerät | `alexa_devices.send_sound` per Gerät (5) | Töne nur über die eigene Aktion           |
| Text-to-Speech          | `notify.<name>` (YAML `platform: tts`)   | Nein                           | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Dauerhafte Benachrichtigung | `notify.persistent_notification`     | Nein                           | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Ja, ohne Titel                 | `mqtt.publish` per Topic (5)                     | Beliebiger Payload                                |

## Eine Person benachrichtigen, nicht ein Gerät { #notifying-a-person-not-a-device }

Home Assistant weiß, wer jede Person ist und welche Geräte-Tracker ihr folgen, aber nicht, wie sie zu erreichen ist.
Das Home-Assistant-Team arbeitet daran, nach der Community-Diskussion „What the Heck?"
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), mit einem
Vorschlag in der [Architektur-Diskussion #1552](https://github.com/home-assistant/architecture/discussions/1552):
Jede Person bekommt eine Liste ihrer Notify-Entitäten, und `notify.send_message` kann an `person.anna` gesendet
werden. Das löst das größte Alltagsproblem, das Telefon in jeder Automatisierung ersetzen zu müssen, und macht
Notify-Entitäten zum natürlichen Weg, jemanden zu erreichen.

Supernotify wird dies so bald wie möglich unterstützen, sobald es veröffentlicht ist, sowohl durch das Senden an eine
Person über ihre verknüpften Notify-Entitäten als auch dadurch, dass `notify.send_message` an eine Person durch das
eigene Routing von Supernotify gehen kann.

## Was Supernotify dagegen tut { #what-supernotify-does-about-it }

Supernotify nimmt eine Benachrichtigung mit einem Satz von Optionen und macht daraus für jeden Kanal den richtigen
Aufruf:

- **Eine Aktion für alles.** `supernotify.notify` nimmt Nachricht, Titel, Bilder, Schaltflächen und Priorität einmal
  entgegen, und jeder [Transport](../../transports/index.md) überträgt, was sein Kanal unterstützt, in die Art, die
  Feldnamen und die Ziele, die seine Integration braucht, ob alte Aktion, Notify-Entität, eigene Aktion oder TTS.
- **Personen, nicht Geräte.** [Recipients](../../configuration/people.md) enthalten E-Mail, Telefonnummer,
  Telegram-Chat usw. jeder Person, und ihre Telefone mit der Companion App werden automatisch gefunden. Benachrichtigen
  Sie `person.anna`, und jeder Kanal bekommt die richtige Adresse. Jeder Recipient bekommt außerdem eine eigene
  Notify-Entität.
- **Wer sie bekommen soll.** Benachrichtigungen können nur an Personen zu Hause oder nur an Abwesende gehen und auf
  andere Kanäle oder Personen ausweichen. Siehe das Rezept
  [Anwesenheitsbasiertes Routing mit Fallback](../../recipes/presence_routing_with_fallback.md).
- **Worum es geht.** [Scenarios](../../configuration/scenarios.md) und Prioritäten bestimmen, welche Kanäle genutzt
  werden, sodass eine Nachricht mit niedriger Priorität nur aufs Telefon geht, während eine kritische auch Gongs
  auslöst und über Lautsprecher gesprochen wird.
- **Nicht zu oft.** [Snooze](../../usage/snoozing.md) und die
  [Duplikaterkennung](../../configuration/dupe_detection.md) verhindern, dass sich dieselbe Meldung wiederholt.
