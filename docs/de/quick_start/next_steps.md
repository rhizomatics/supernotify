---
title: Wie es weitergeht
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: Was nach der ersten Supernotify-Benachrichtigung kommt - aus einer Automatisierung benachrichtigen, ein Dashboard hinzufügen, wählen, wer und was benachrichtigt wird, und Ideen in den Rezepten finden
---
# Wie es weitergeht

Beginnen Sie mit einer Automatisierung, denn dafür sind Benachrichtigungen da. Alles Weitere ist optional und in beliebiger Reihenfolge möglich.

## Eine Benachrichtigung in eine Automatisierung einbauen { #add-a-notification-to-an-automation }

`supernotify.notify` ist eine Aktion wie jede andere und kommt auf dem üblichen Weg in eine Automatisierung. Dieses Beispiel sendet eine Benachrichtigung, wenn ein Bewegungsmelder im Flur auslöst.

Legen Sie eine Automatisierung mit dem Bewegungsmelder als Auslöser an, wählen Sie dann **Aktion hinzufügen** und suchen Sie nach Supernotify:

![Aktion auswählen](../../assets/images/add_action_automation.png){width=600}

Tragen Sie die Nachricht ein und alles Weitere aus [der ersten Benachrichtigung](first_notification.md), etwa ein Ziel oder eine Delivery:

![Aktion konfigurieren](../../assets/images/automation_action_simple.png){width=600}

```yaml title="Automatisierung mit Bewegungsmelder"
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

Soll es auch über die Lautsprecher zu hören sein, fügen Sie `alexa_devices_announce_all` und `mobile_push` als Deliveries hinzu. [Benachrichtigungen senden](../../usage/notifying.md) beschreibt alles, was die Aktion sonst noch kann.

Ein ausführlicheres Beispiel mit Sprachansagen und Kamerabild zeigt das Rezept [Jemand ist an der Tür](../../recipes/someone_at_the_door.md).

## Ein Dashboard hinzufügen { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) bietet viele gezielte Dashboard-Karten, um Benachrichtigungen zu steuern und zu überwachen, von Hand zu versenden oder Konfigurationen zu testen.

![Übersichts- und Transport-Karten](../../assets/images/cards.png)

Die Seite [Dashboard](../../configuration/dashboard.md) enthält ein vollständiges Beispiel zum Einfügen in ein neues Dashboard, das sich anschließend visuell bearbeiten lässt.

## Personen und Deliveries ein- und ausschalten { #switch-people-and-deliveries-on-and-off }

Jede Person, die Supernotify kennt, hat eine `switch`-Entität in Home Assistant, ebenso jede Delivery. Schalten Sie eine aus, um jemanden nicht zu stören oder die Lautsprecher eine Weile stummzuschalten, ohne Automatisierungen zu ändern.

## Nur bestimmte Geräte benachrichtigen { #notify-just-some-devices }

Ziele können neben einer Person oder einem Gerät auch ein **Bereich**, eine **Etage** oder ein **Label** sein. So geht eine Benachrichtigung an die Lautsprecher im Erdgeschoss oder an alles mit dem Label für die Küche. Siehe [Targets](../../usage/targets.md) und die [FAQs](../../faqs.md) für häufige Fragen.

## Die Einstellungen anpassen { #tune-the-settings }

Archivierung, Duplikaterkennung und Aufräumen lassen sich über die Option **Konfigurieren** der Integration unter **Einstellungen → Geräte & Dienste** ändern. Siehe [Archivierung](../../configuration/archiving.md) und [Duplikaterkennung](../../configuration/dupe_detection.md).

## Lassen Sie sich inspirieren { #be-inspired }

Viele Ideen mit Beispielkonfiguration finden Sie in den [Rezepten](../../recipes/index.md).

## Mit YAML weitergehen { #go-further-with-yaml }

Mit etwas YAML-Konfiguration ist mehr möglich, und alles davon ist optional:

- Personen eine E-Mail-Adresse oder Telefonnummer geben, unter [People](../../configuration/people.md)
- Eigene Deliveries anlegen, etwa eine HTML-E-Mail oder eine feste Gruppe von Lautsprechern, unter [Deliveries](../../configuration/deliveries.md)
- Das Verhalten von Benachrichtigungen nachts oder bei leerem Haus ändern, mit [Scenarios](../../configuration/scenarios.md)
- Kamerabilder anhängen, unter [Multimedia](../../configuration/multimedia.md)

[Fortgeschrittene Konzepte](advanced_concepts.md) erklärt die Ideen dahinter, und [Konfiguration](../../configuration/index.md) ist die Referenz.

## Hilfe bekommen { #get-help }

Fragen Sie auf der Seite [Discussions](https://github.com/rhizomatics/supernotify/discussions) oder nutzen Sie einen KI-Agenten - siehe die letzte Antwort in den [FAQs](../../faqs.md).
