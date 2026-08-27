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
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Toevoegen aan HACS">
   </a>
<br/>
<br/>
<br/>

**Uniforme Meldingen voor Home Assistant**

### GROTE WIJZIGING v2.0.0

>> `2.0.0` van SuperNotify stapt over op een native Home Assistant UI-configuratie ('ConfigFlow'). Als je al een eenvoudige configuratie hebt, wordt alles automatisch voor je gemigreerd en is er geen YAML meer nodig.

>> Als je een geavanceerde configuratie hebt (bezorgingen, scenario's, camera's, personen, acties enz.), wordt er een *reparatie* aangemaakt om deze naar een nieuw bestand `supernotify.yaml` te verplaatsen en een `include`-instructie aan je `configuration.yaml` toe te voegen. Of je kunt ervoor kiezen om de configuratie handmatig uit het `notify`-blok te halen, zoals jij dat wilt.

>> In beide gevallen wordt er niets verwijderd of uitgecommentarieerd, zodat de wijziging eenvoudig terug te draaien is. Verwijder de oude configuratie zodra je er zeker van bent dat de nieuwe versie voor jou werkt.

Een **uniforme meldingsinterface** bovenop het ingebouwde `notify`-platform van Home Assistant, om meerdere meldingskanalen en complexe scenario's sterk te vereenvoudigen, inclusief meerkanaalsmeldingen, voorwaardelijke meldingen, mobiele acties, camera-snapshots, geluidssignalen en op sjablonen gebaseerde HTML-e-mails.

Supernotify heeft één doel: **de eenvoudigst mogelijke melding zo veel meldingen laten versturen als nodig, zonder code en met minimale configuratie**.

Dit houdt automatiseringen, scripts en AppDaemon-apps eenvoudig en onderhoudsvriendelijk, waarbij alle details en regels op één plek worden beheerd. De kleinste mogelijke melding — alleen een bericht — kan genoeg zijn om alles in gang te zetten. Wijzig e-mailadressen op één plek en laat Supernotify bepalen welke mobiele apps gebruikt worden.

Met alleen de UI-configuratie start u direct met mobiele pushmeldingen naar iedereen in huis, zonder dat u de namen van mobiele apps in meldingen hoeft te configureren.


## Distributie

Supernotify is een aangepast component beschikbaar via de [Home Assistant Community Shop](https://hacs.xyz) (**HACS**). Het is gratis en open source onder de [Apache 2.0-licentie](https://www.apache.org/licenses/LICENSE-2.0).

## Documentatie

Bekijk [Aan de slag](https://supernotify.rhizomatics.org.uk/getting_started/), de uitleg van [kernconcepten](https://supernotify.rhizomatics.org.uk/concepts/) en de beschikbare [transportadapters](https://supernotify.rhizomatics.org.uk/transports/). [Meldingen versturen](https://supernotify.rhizomatics.org.uk/usage/notifying/) laat zien hoe u Supernotify aanroept vanuit automatiseringen of de ontwikkelaarstools.

Er zijn veel [recepten](https://supernotify.rhizomatics.org.uk/recipes/) met voorbeeldconfiguraties, of blader op [tags](https://supernotify.rhizomatics.org.uk/tags/).


## Functies

* Één actie -> Meerdere meldingen
    * Verwijder repetitieve configuratie en code uit automatiseringen
    * Adapters stemmen meldingsgegevens automatisch af op elke integratie
    * Gebruik bijvoorbeeld met een [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) om camera-snapshots per e-mail te ontvangen
* Automatische installatie
    * Bezorgingsconfiguratie voor mobiele push, e-mail (SMTP) en meldingsentiteiten worden automatisch ingesteld
    * Mobiele apps worden automatisch gevonden, inclusief fabrikant en model van de telefoon
    * Alexa-apparaten voor geluidssignalen worden automatisch ontdekt
* Verder dan `notify`-integraties
    * Geluidssignalen, sirenes, sms, TTS, Alexa-aankondigingen en geluiden, API-aanroepen, MQTT-apparaten, Gotify, ntfy
    * Alle standaard `notify`- en `notify.group`-implementaties beschikbaar
    * Sterk vereenvoudigd gebruik van mobiele pushmeldingen, bijv. voor iPhone
* Voorwaardelijke meldingen
    * Met standaard Home Assistant `conditions`
    * Extra conditievariabelen toegevoegd, inclusief bericht en prioriteit
    * Combineer met bezettingsdetectie voor meldingen op basis van aanwezigheid, berichtprioriteit en berichtinhoud
* **Scenario's** voor eenvoudige beknopte configuratie
    * Bundel veelgebruikte configuratieblokken en voorwaardelijke logica
    * Pas toe op verzoek (`red_alert`, `nerdy`) of automatisch op basis van voorwaarden
* Uniform persoonmodel
    * Definieer een e-mail, sms-nummer of mobiel apparaat en gebruik daarna de `person`-entiteit in meldingsacties
    * Personen worden automatisch geconfigureerd samen met hun mobiele apps
* Eenvoudige **HTML e-mailsjablonen**
    * Standaard Home Assistant Jinja2, gedefinieerd in YAML-configuratie, actieaanroepen of als losse bestanden
    * Standaard algemeen sjabloon meegeleverd
* **Mobiele acties**
    * Stel één consistente set mobiele acties in voor meerdere meldingen
    * Inclusief *sluimer*acties om te dempen op basis van criteria
* Flexibele **afbeeldingssnapshots**
    * Ondersteunt camera's, MQTT-afbeeldingen en afbeeldings-URL's
    * Herpositioneer camera's naar PTZ-presets voor en na een snapshot
* Kiezen van configuratieniveau
    * Stel standaarden in op transport-, bezorgings- en actieniveau
* **Dubbele melding**-onderdrukking
    * Stel in hoe lang te wachten voor hertoelating
* Melding **archivering** en **foutopsporingsondersteuning**
    * Archiveer meldingen optioneel naar bestandssysteem en/of MQTT-topic
    * Inclusief volledige foutopsporingsinformatie
    * Bezorgingen, transporten, ontvangers en scenario's zichtbaar als entiteiten in de Home Assistant UI


## YAML alleen voor geavanceerd gebruik

Supernotify ondersteunt momenteel standaard Home Assistant UI-configuratie voor de basisinstelling, en [YAML-configuratie](https://supernotify.rhizomatics.org.uk/configuration/yaml/) voor geavanceerde functies. YAML blijft behouden om het werken met grotere regelsets te vergemakkelijken.

Met de eenvoudige niet-YAML-configuratie kan al veel worden bereikt, inclusief automatisering van de mobiele push-instelling. Zie de [recepten](recipes/index.md) in de documentatie, en dit mobiele push-voorbeeld:

```yaml title="Met nul YAML, alles via de UI geconfigureerd"
  - action: notify.supernotify
    data:
        message: Hallo! Dit is een test van Supernotify die naar ieders mobiele apps stuurt
```


##  Rhizomatics Open Source voor Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Automatisch Home Assistant alarmcontrolepanelen in- en uitschakelen met fysieke knoppen, aanwezigheid, agenda's en meer
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - OpenTelemetry (OTLP) en Syslog-gebeurtenisregistratie voor Home Assistant


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integreer met ANPR/ALPR kentekenplaatcamera's via bestandssysteem naar MQTT
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatisch meldingen via MQTT bij Docker-image-updates

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
