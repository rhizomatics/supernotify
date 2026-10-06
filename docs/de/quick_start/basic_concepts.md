---
title: Grundkonzepte
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: Die wenigen Supernotify-Konzepte für den Einstieg - Ziele, Recipients, Deliveries und Priorität, und wie sie zusammenspielen
---
# Grundkonzepte

## So greift alles ineinander { #how-it-fits-together }

Eine einzige Benachrichtigung aus einer Automatisierung kann zu mehreren unterschiedlichen Benachrichtigungen werden, jede passend zu dem Weg, auf dem sie verschickt wird.

![Eine Benachrichtigung aus einer Automatisierung wird zu einer E-Mail, zwei Push-Nachrichten, einer SMS und einer Lautsprecheransage](../../assets/images/concepts_flow.svg)

Das Bild von links nach rechts gelesen:

1. **Wer benachrichtigt wird** - die [Ziele](#target). Personen werden anhand ihrer [Recipient](#recipient)-Angaben in die Wege umgewandelt, über die sie erreichbar sind
2. **Delivery** - die passenden [Deliveries](#delivery) werden ausgewählt, standardmäßig oder weil Sie sie verlangt haben
3. **Benachrichtigungen** - jede Delivery nimmt sich die Ziele, die sie verwenden kann, und sendet eine dafür passende Benachrichtigung, sodass eine E-Mail ein vollständiges HTML-Layout mit Bildern haben kann, während der Küchenlautsprecher eine kurze gesprochene Nachricht erhält

Drei Begriffe decken fast alles ab, wenn nur die Oberfläche genutzt wird.

## Ziel (Target) { #target }

Ein Ziel ist, **wer oder was benachrichtigt wird**: eine Person, ein Telefon, ein Lautsprecher, eine E-Mail-Adresse oder ein Bereich, eine Etage oder ein Label, das für mehrere Geräte steht.

Ohne Ziele geht die Benachrichtigung an alle.

## Empfänger (Recipient) { #recipient }

Ein Recipient ist **eine Person, wie Supernotify sie kennt**: ihre Telefone und Tablets und optional eine E-Mail-Adresse und Telefonnummer. Recipients werden automatisch aus den *Person*-Entitäten in Home Assistant ermittelt.

Ein Recipient ist keine andere Art von Ziel. Eine Person ist eines der Dinge, die ein Ziel sein kann, und beim Recipient schlägt Supernotify nach, wie sie zu erreichen ist. Deshalb funktioniert `person.joe_mctest` als Ziel, und Joes E-Mail-Adresse muss nicht in jeder Automatisierung stehen.

## Zustellung (Delivery) { #delivery }

Eine Delivery ist **ein Weg, eine Benachrichtigung zu senden**, mit einem Namen wie `mobile_push`, `email` oder `alexa_devices_announce_all`. Supernotify legt Deliveries für alles an, was es in Ihrem Home Assistant findet, und sie erscheinen im Feld **Delivery** der Aktion `supernotify.notify`.

Ohne Angabe von Deliveries verwendet Supernotify diejenigen, die selbst herausfinden können, wohin gesendet wird, etwa Mobile Push und E-Mail.

## Priorität (Priority) { #priority }

Die Priorität gibt an, **wie dringend eine Benachrichtigung ist**, in fünf Stufen: `minimum`, `low`, `medium`, `high` und `critical`. Sie ist optional und ohne Angabe `medium`. Die Priorität wird an Telefone, E-Mail-Programme und alles andere weitergegeben, das sie versteht.

## Zwei weitere, für später { #two-more-for-later }

Diese tauchen überall in der Dokumentation auf, für den Einstieg wird keiner von beiden gebraucht.

- Ein **Transport** ist das technische Mittel hinter einer Delivery, meist eine Home Assistant-Integration wie die Mobile App, SMTP oder Alexa Devices. Eine Delivery ist ein Transport samt den Einstellungen dafür, sodass ein Transport mehrere Deliveries haben kann, etwa eine einfache `email` und eine `html_email`.
- Ein **Scenario** ist ein benanntes Paket von Einstellungen, das ändert, welche Deliveries verwendet werden und wie sie sich verhalten, zum Beispiel leiser in der Nacht. Scenarios werden in YAML eingerichtet.

[Fortgeschrittene Konzepte](advanced_concepts.md) behandelt beide und alles Weitere, was die YAML-Konfiguration kann.
