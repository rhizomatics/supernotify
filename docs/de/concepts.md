---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Kernkonzepte von Supernotify für Home Assistant, einschließlich Transport, Delivery, Scenario und Recipient
---
# Kernkonzepte

## So greift alles ineinander { #how-it-fits-together }

Eine einzige Benachrichtigung aus einer Automatisierung kann zu mehreren unterschiedlichen Benachrichtigungen werden,
jede passend zu dem Weg, auf dem sie verschickt wird.

![Eine Benachrichtigung aus einer Automatisierung wird zu einer E-Mail, zwei Push-Nachrichten, einer SMS und einer Lautsprecheransage](../assets/images/concepts_flow.svg)

1. **Ziele** - Personen werden anhand ihrer [Recipient](#recipient)-Angaben in die Wege umgewandelt, über die sie erreichbar sind
2. **Deliveries** - die passenden [Deliveries](#delivery) werden ausgewählt, standardmäßig oder über [Scenarios](#scenario)
3. **Benachrichtigungen** - jede Delivery nimmt sich die Ziele, die sie verwenden kann, und sendet eine dafür passende Benachrichtigung,
   sodass eine E-Mail ein vollständiges HTML-Layout mit Bildern haben kann, während der Küchenlautsprecher eine kurze gesprochene Nachricht erhält

## Ziel (Target) { #target }
- Wer oder was benachrichtigt wird und wie
  - *Direkte* Ziele
    - E-Mail-Adresse
    - Telefonnummer
    - `entity_id` oder `device_id`, zum Beispiel für eine Ansage über ein Alexa-Gerät
    - eine eigene ID für einen speziellen Transport wie Telegram
  - *Indirekte* Ziele, die in direkte Ziele umgewandelt werden können
    - `person_id`, um die *Recipient*-Funktionen zu nutzen
    - die Standard-Zielauswahl von Home Assistant, `label_id`, `floor_id` und `area_id`
    - *Gruppen*-Ziele (sowohl neue als auch alte Home Assistant-Gruppen)
- Ziele können einer bestimmten **Zielkategorie** zugeordnet werden, etwa `discord_channel:839439434`, siehe [Kategorie-Präfixe](../usage/targets.md#category-prefixes)
- Jedes Ziel wird von der am besten geeigneten Integration aus der Liste übernommen
  - Zum Beispiel wird eine Notify-Entität eines Alexa-Geräts vom Alexa Devices-Transport verarbeitet, während eine allgemeine Notify-Entität auf den weniger leistungsfähigen Notify Entity-Transport zurückfällt
- Siehe [Targets](../usage/targets.md) für weitere Informationen

## Empfänger (Recipient) { #recipient }
- Eine Person, mit optionaler E-Mail-Adresse, Telefonnummer, Mobilgeräten oder eigenen Zielen
  - Standardmäßig automatisch aus den Benutzerkonten und Personen-Entitäten in Home Assistant erkannt
- So lassen sich Personen in Automatisierungen leichter ansprechen: `person.joe_mctest` statt sich in jeder Automatisierung Joes E-Mail-Adresse merken zu müssen. Funktioniert auch für Telefonnummern, wenn eine passende SMS-Integration installiert ist, oder für eigene Kennungen wie Telegram oder Discord
- Jeder Empfänger hat außerdem eine Home Assistant-`switch`-Entität, sodass man jemanden leicht vor Benachrichtigungen verschonen kann
- Siehe [People](../configuration/people.md) und [Recipes](../recipes/index.md) für weitere Details

## Transport { #transport }

- Ein *Transport* ist das technische Mittel, mit dem tatsächlich benachrichtigt wird, meist über eine der bereits installierten Home Assistant-Integrationen
- *Transport-Adapter* machen den Unterschied zwischen normalen Notify-Gruppen und Supernotify aus
  - Eine Notify-Gruppe scheint einfache Mehrkanal-Benachrichtigungen zu ermöglichen, doch in der Praxis hat jeder Notify-Transport andere `data`-Strukturen (und `data` innerhalb von `data`!), Adressierung usw., sodass Benachrichtigungen am Ende auf den kleinsten gemeinsamen Nenner reduziert werden, etwa nur `message`!
- Supernotify bringt Adapter für gängige Transports wie E-Mail, Mobile Push, SMS und Alexa mit, sowie einen *Generic*-Transport-Adapter, mit dem sich jede andere Home Assistant-Aktion einbinden lässt
- Der Transport-Adapter ermöglicht es, eine einzige Benachrichtigung an viele Plattformen zu senden, auch wenn diese völlig unterschiedliche und untereinander inkompatible Schnittstellen haben
- Er passt Benachrichtigungen an den Transport an, entfernt Attribute, die dieser nicht akzeptiert, formt `data`-Strukturen um, wählt nur die passenden Ziele aus und erlaubt, wo möglich, weitere Feinabstimmung
- Jeder Transport hat eine Standardkonfiguration, mit der sich vieles feinabstimmen und vorbelegen lässt, sodass nicht in jeder Benachrichtigung dieselben Werte angegeben werden müssen
- Siehe [Transports](../transports/index.md) für weitere Details

## Zustellung (Delivery) { #delivery }

- Eine **Delivery** legt jeden Benachrichtigungskanal fest, den Sie verwenden möchten
  - Von Haus aus hat jeder Transport eine Delivery mit demselben Namen, zum Beispiel `email` oder `mobile_push`
  - Manche Transports legen automatisch zusätzliche Deliveries an, etwa `alexa_devices_announce_all` oder `chime_siren_all`
  - Per YAML lassen sich weitere Deliveries anlegen, zum Beispiel `html_email` zusätzlich zur Klartext-`email`, oder eigene Deliveries für bestimmte Sprachassistenten
- Transports, die Ziele eindeutig auswählen können, wie E-Mail, Mobile Push, SMS, Alexa Devices und Notify Entity, werden standardmäßig bei der Verarbeitung von Zielen berücksichtigt
  - Andere können per Konfiguration, über Scenarios oder auf Anforderung in einer Benachrichtigung einbezogen werden
- Sie können eigene Deliveries mit selbst gewählten Namen anlegen und mehrere Deliveries für einen Transport haben, zum Beispiel `plain_email` und `html_email`
- Der [Generic-Transport](../transports/generic.md) dient als *Werkzeugkasten*, um eine Delivery für fast alles zu erstellen, was Home Assistant kann und was noch nicht von einem Standard-Transport abgedeckt wird
- Siehe [Deliveries](../configuration/deliveries.md) und [Recipes](../recipes/index.md) für weitere Details

## Szenario (Scenario) { #scenario }
- Ein Paket von Einstellungen, das per Name oder automatisch über Home Assistant-Bedingungen eingeschaltet werden kann
- Scenarios können manuell über einen `apply_scenarios`-Wert im `data`-Block der Benachrichtigung ausgewählt werden, oder automatisch über einen standardmäßigen Home Assistant-`conditions`-Block
  - Bedingungen können den Text der Nachricht einbeziehen, sodass eine Frigate-Meldung über Vögel auf der Terrasse anders behandelt werden kann als ein Einbrecher am Fenster
- Mit Scenarios werden Benachrichtigungen nachts dezenter, an Feiertagen festlicher, oder bestimmte Nachrichten erhalten Vorrang
- Sie ermöglichen es, Anpassungen an einer Stelle für viele Deliveries oder Benachrichtigungen vorzunehmen, und sind der Schlüssel, um Benachrichtigungsaufrufe in Automatisierungen radikal zu vereinfachen
- Siehe [Scenarios](../configuration/scenarios.md) und [Recipes](../recipes/index.md) für weitere Details

## Priorität (Priority) { #priority }
- Eine Dringlichkeitsstufe für Benachrichtigungen
   - Es gibt weder innerhalb noch außerhalb von Home Assistant einen Standard für die Priorisierung von Benachrichtigungen
   - Supernotify hat ein eigenes 5-stufiges Schema nach gängiger Praxis, von `minimum` bis `critical`
   - Die Priorität kann etwa für Scenario- und Delivery-Regeln genutzt und an Notify-Integrationen weitergegeben werden, die sie unterstützen
   - Supernotify hat eine eigene E-Mail-Integration, die die Priorität so übersetzt, dass Outlook, Apple Mail usw. sie verstehen

!!! info
    Für technisch Interessierte gibt es ein [Klassendiagramm](../developer/class_diagram.md) der Kernklassen zu diesen Konzepten.

# Grundprinzipien { #core-principles }

1. Eine Benachrichtigung braucht nur eine Nachricht, alles andere kann vorbelegt werden, einschließlich aller Ziele
2. Was in einem Aktionsaufruf angegeben wird, hat Vorrang vor den Standardwerten
   - Dies lässt sich z. B. über `target_usage` anpassen
   - Das Personenverzeichnis wird nur dann zum Erzeugen von Zielen verwendet, wenn keine Ziele angegeben sind
3. Aktion > Scenario > Delivery > Transport für Konfiguration und Standardwerte
4. So unkompliziert wie möglich in Konfiguration und Aufruf
   - Ziele können in Unterkategorien gegliedert werden oder eine große Liste aus Entitäts-IDs, Geräte-IDs, E-Mail-Adressen und Telefonnummern sein
   - Optionen im Aktions-`data` wie `delivery` können ein einzelner Wert, eine Liste oder eine Zuordnung sein

## Entwickler { #developers }

Siehe [Developer Concepts](../developer/concepts.md) dazu, wie Benachrichtigungen durch Deliveries, Ziele und *Envelopes* laufen, sowie die [Design Principles](../developer/principles.md).
