---
title: Die erste Benachrichtigung senden
tags:
  - quickstart
  - developer tools
  - notification
description: Eine erste Supernotify-Benachrichtigung aus Home Assistant senden - an alle, an eine Person und an Alexa-Lautsprecher
---
# Die erste Benachrichtigung senden

Alles auf dieser Seite geschieht in der Oberfläche von Home Assistant, direkt nach der [Installation](installation.md). Jeder Schritt zeigt auch das YAML, für alle, die das bevorzugen.

## 1. Alle benachrichtigen { #1-notify-everyone }

Öffnen Sie den [Reiter Aktionen](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab) in den **Entwicklerwerkzeugen**, wählen Sie die Aktion `supernotify.notify`, geben Sie eine Nachricht ein und drücken Sie **Aktion ausführen**.

![Aktion in den Entwicklerwerkzeugen](../../assets/images/tools_action_notify.png){width=600}

```yaml title="Nachricht an alle"
action: supernotify.notify
data:
  message: Something went off in the basement
```

Eine Benachrichtigung braucht nur eine Nachricht. Ohne weitere Angaben geht sie an jedes Telefon und Tablet mit der Home Assistant-App, für alle im Haus.

## 2. Eine Person benachrichtigen { #2-notify-one-person }

Das sind vermutlich mehr Leute als gewünscht. Um es einzugrenzen, wählen Sie `person`-Entitäten oder einzelne Mobilgeräte als **Ziele** (targets):

![Alle Mobilgeräte einer Person benachrichtigen](../../assets/images/person_notify.png){width=400}

```yaml title="Nachricht an eine Person"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

Jetzt bekommen nur Johns Geräte die Nachricht. Wer eine Person statt eines Telefons wählt, erreicht John auch dann noch, wenn er ein neues Telefon hat.

## 3. Den Versandweg wählen { #3-choose-how-its-sent }

Das Feld **Delivery** listet die Wege auf, die Supernotify zum Senden gefunden hat. Lassen Sie es weg, wählt Supernotify für Sie; wählen Sie daraus, werden nur diese verwendet.

![Auswahl der Delivery](../../assets/images/delivery_choice.png)

Mit Alexa-Geräten verwenden Sie `alexa_devices_announce_all` oder `alexa_devices_speak_all`. (Announce spielt vor der Ansage einen Signalton, Speak nicht.) Beides lässt sich in einer einzigen Benachrichtigung mit E-Mail und Mobile Push kombinieren.

```yaml title="Lautsprecher und Telefone zusammen"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

Jeder Weg bekommt eine passende Benachrichtigung: Die Lautsprecher sagen die Nachricht an, die Telefone zeigen sie.

Wenn das funktioniert, ist der nächste Schritt, [eine Benachrichtigung in eine Automatisierung einzubauen](next_steps.md#add-a-notification-to-an-automation).
