![Supernotify](../assets/images/dark_icon.png){ align=left }

# Supernotify

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)

 <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=rhizomatics&repository=supernotify" target="_blank" rel="noopener noreferrer">
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Zu HACS hinzufügen">
   </a>
<br/>
<br/>
<br/>

**Einheitliche Benachrichtigungen für Home Assistant**

Eine **einheitliche Benachrichtigungsschnittstelle** auf Basis der integrierten `notify`-Plattform von Home Assistant, um mehrere Benachrichtigungskanäle und komplexe Szenarien erheblich zu vereinfachen, einschließlich Mehrkanal-Benachrichtigungen, bedingter Benachrichtigungen, mobiler Aktionen, Kamera-Snapshots, Klingeltöne und vorlagenbasierter HTML-E-Mails.

Supernotify hat ein einziges Ziel: **mit der einfachstmöglichen Benachrichtigung so viele Benachrichtigungen wie nötig auszulösen, ohne Code und mit minimaler Konfiguration**.

Dies hält Automatisierungen, Skripte und AppDaemon-Apps einfach und wartungsfreundlich, wobei alle Details und Regeln an einem Ort verwaltet werden. Die kleinstmögliche Benachrichtigung — nur eine Nachricht — kann ausreichen, um alles auszulösen. Ändern Sie E-Mail-Adressen an einer Stelle und lassen Sie Supernotify herausfinden, welche mobilen Apps verwendet werden sollen.

Nur mit der UI-Konfiguration beginnen Sie sofort mit mobilen Push-Benachrichtigungen an alle im Haus registrierten Personen, ohne die Namen der mobilen Apps in Benachrichtigungen zu konfigurieren.


## Verteilung

Supernotify ist ein benutzerdefiniertes Komponent, das über den [Home Assistant Community Shop](https://hacs.xyz) (**HACS**) verfügbar ist. Es ist kostenlos und quelloffen unter der [Apache 2.0-Lizenz](https://www.apache.org/licenses/LICENSE-2.0).

## Dokumentation

Starten Sie mit [Erste Schritte](https://supernotify.rhizomatics.org.uk/getting_started/), der Erklärung der [Kernkonzepte](https://supernotify.rhizomatics.org.uk/concepts/) und den verfügbaren [Transport-Adaptern](https://supernotify.rhizomatics.org.uk/transports/). [Benachrichtigen](https://supernotify.rhizomatics.org.uk/usage/notifying/) zeigt, wie Sie Supernotify aus Automatisierungen oder der Entwicklertools-Aktionsseite aufrufen.

Es gibt viele [Rezepte](https://supernotify.rhizomatics.org.uk/recipes/) mit Beispielkonfigurationen oder durchsuchen Sie nach [Tags](https://supernotify.rhizomatics.org.uk/tags/).


## Funktionen

* Eine Aktion -> Mehrere Benachrichtigungen
    * Entfernen Sie repetitive Konfiguration und Code aus Automatisierungen
    * Adapter passen Benachrichtigungsdaten automatisch für jede Integration an
    * Verwenden Sie es z. B. mit einem [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) für Kamera-Snapshots per E-Mail
* Automatische Einrichtung
    * Lieferungskonfiguration für mobile Push-, E-Mail- (SMTP) und Benachrichtigungsentitäten wird automatisch eingerichtet
    * Mobilen Apps werden automatisch erkannt, einschließlich Hersteller und Modell des Telefons
    * Alexa-Geräte für Klingeltöne werden automatisch erkannt
* Über `notify`-Integrationen hinaus
    * Klingeltöne, Sirenen, SMS, TTS, Alexa-Ankündigungen und -Töne, API-Aufrufe, MQTT-Geräte,  Gotify, ntfy
    * Alle Standard-`notify`- und `notify.group`-Implementierungen verfügbar
    * Stark vereinfachte Nutzung von mobilen Push-Benachrichtigungen, z. B. für iPhone
* Bedingte Benachrichtigungen
    * Verwendung von Standard Home Assistant `conditions`
    * Zusätzliche Bedingungsvariablen hinzugefügt, einschließlich Nachricht und Priorität
    * Kombination mit Anwesenheitserkennung für kontextabhängige Benachrichtigungen
* **Szenarien** für einfache, prägnante Konfiguration
    * Bündeln Sie häufig verwendete Konfigurationsblöcke und bedingte Logik
    * Auf Abruf anwenden (`red_alert`, `nerdy`) oder automatisch basierend auf Bedingungen
* Einheitliches Personenmodell
    * Definieren Sie eine E-Mail, SMS-Nummer oder ein mobiles Gerät und verwenden Sie dann die `person`-Entität in Benachrichtigungsaktionen
    * Personen werden automatisch mit ihren mobilen Apps konfiguriert
* Einfache **HTML-E-Mail-Vorlagen**
    * Standard Home Assistant Jinja2, definiert in der YAML-Konfiguration, Aktionsaufrufen oder als eigenständige Dateien
    * Standardvorlage mitgeliefert
* **Mobile Aktionen**
    * Richten Sie einen einheitlichen Satz mobiler Aktionen für mehrere Benachrichtigungen ein
    * Enthält *Schlummern*-Aktionen zum Stummschalten nach Kriterien
* Flexible **Bild-Snapshots**
    * Unterstützt Kameras, MQTT-Bilder und Bild-URLs
    * Kameras vor und nach einem Snapshot auf PTZ-Voreinstellungen repositionieren
* Wahl des Konfigurationsniveaus
    * Standardwerte auf Transport-, Liefer- und Aktionsebene festlegen
* Unterdrückung **doppelter Benachrichtigungen**
    * Einstellbare Wartezeit vor erneuter Zulassung
* Benachrichtigungs-**Archivierung** und **Debug-Unterstützung**
    * Optionale Archivierung von Benachrichtigungen ins Dateisystem und/oder MQTT-Topic
    * Enthält vollständige Debug-Informationen
    * Lieferungen, Transporte, Empfänger und Szenarien als Entitäten in der Home Assistant-Oberfläche


## YAML nur für erweiterte Nutzung

Supernotify unterstützt derzeit die standardmäßige Home Assistant UI-Konfiguration für die Basiseinrichtung sowie [YAML-Konfiguration](https://supernotify.rhizomatics.org.uk/configuration/yaml/) für erweiterte Funktionen. YAML bleibt erhalten, um die Arbeit mit größeren Regelwerken zu erleichtern.

Mit der einfachen Nicht-YAML-Konfiguration lässt sich bereits viel erreichen, einschließlich der automatischen Einrichtung von Mobile Push. Siehe die [Rezepte](recipes/index.md) in der Dokumentation, sowie dieses Mobile-Push-Beispiel:

```yaml title="Mit null YAML, alles per UI konfiguriert"
  - action: notify.supernotify
    data:
        message: Hallo! Test von Supernotify, das an alle mobilen Apps sendet
```


##  Rhizomatics Open Source für Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Automatisches Aktivieren und Deaktivieren von Home Assistant Alarmsteuerpanelen mit physischen Tasten, Anwesenheit, Kalendern und mehr
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - OpenTelemetry (OTLP) und Syslog-Ereigniserfassung für Home Assistant


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integration mit ANPR/ALPR-Kennzeichenkameras über das Dateisystem zu MQTT
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatische Benachrichtigung über MQTT bei Docker-Image-Updates

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
