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
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Aggiungi a HACS">
   </a>
<br/>
<br/>
<br/>

**Notifiche Unificate per Home Assistant**

Un'**interfaccia di notifica unificata** sulla piattaforma `notify` integrata di Home Assistant, per semplificare notevolmente i canali di notifica multipli e gli scenari complessi, incluse notifiche multicanale, notifiche condizionali, azioni mobili, snapshot delle telecamere, carillon ed e-mail HTML basate su modelli.

Supernotify ha un solo obiettivo: **fare in modo che la notifica più semplice possibile invii tutte le notifiche necessarie, senza codice e con configurazione minima**.

Questo mantiene le automazioni, gli script e le app AppDaemon semplici e facili da mantenere, con tutti i dettagli e le regole gestiti in un unico posto. La notifica più piccola possibile — solo un messaggio — può essere sufficiente per attivare tutto. Cambia gli indirizzi e-mail in un unico posto e lascia che Supernotify determini quali app mobili utilizzare.

Con la sola configurazione dell'interfaccia, avvia le notifiche push mobili a tutti i registrati in casa, senza configurare i nomi delle app mobili nelle notifiche.


## Distribuzione

Supernotify è un componente personalizzato disponibile tramite il [Home Assistant Community Shop](https://hacs.xyz) (**HACS**). È gratuito e open source sotto la [licenza Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0).

## Documentazione

Prova [Iniziare](https://supernotify.rhizomatics.org.uk/getting_started/), la spiegazione dei [concetti fondamentali](https://supernotify.rhizomatics.org.uk/concepts/) e gli [adattatori di trasporto](https://supernotify.rhizomatics.org.uk/transports/) disponibili. [Notifiche](https://supernotify.rhizomatics.org.uk/usage/notifying/) mostra come chiamare Supernotify dalle automazioni o dalla pagina degli strumenti per sviluppatori.

Ci sono molte [ricette](https://supernotify.rhizomatics.org.uk/recipes/) con esempi di configurazione, o sfoglia per [tag](https://supernotify.rhizomatics.org.uk/tags/).


## Funzionalità

* Un'azione -> Più notifiche
    * Rimuovi configurazioni e codice ripetitivi dalle automazioni
    * Gli adattatori sintonizzano automaticamente i dati di notifica per ogni integrazione
    * Ad esempio, usa con un [Blueprint Frigate](https://github.com/SgtBatten/HA_blueprints) per ricevere snapshot delle telecamere via e-mail
* Configurazione automatica
    * Configurazione di consegna per notifiche push mobili, e-mail (SMTP) ed entità di notifica impostata automaticamente
    * App mobili scoperte automaticamente, inclusi produttore e modello del telefono
    * Dispositivi Alexa per carillon scoperti automaticamente
* Oltre le integrazioni `notify`
    * Carillon, sirene, SMS, TTS, annunci e suoni Alexa, chiamate API, dispositivi MQTT,  Gotify, ntfy
    * Tutte le implementazioni standard `notify` e `notify.group` disponibili
    * Uso notevolmente semplificato delle notifiche push mobili, ad es. per iPhone
* Notifiche condizionali
    * Usando le `conditions` standard di Home Assistant
    * Variabili di condizione aggiuntive aggiunte, inclusi messaggio e priorità
    * Combina con il rilevamento dell'occupazione per personalizzare le notifiche
* **Scenari** per una configurazione semplice e concisa
    * Raggruppa blocchi comuni di configurazione e logica condizionale
    * Applica su richiesta (`red_alert`, `nerdy`) o automaticamente in base a condizioni
* Modello unificato delle persone
    * Definisci un'e-mail, un numero SMS o un dispositivo mobile, poi usa l'entità `person` nelle azioni di notifica
    * Le persone vengono auto-configurate insieme alle loro app mobili
* **Modelli e-mail HTML** facili
    * Jinja2 standard di Home Assistant, definito nella configurazione YAML, nelle chiamate di azione o come file autonomi
    * Modello generale predefinito fornito
* **Azioni mobili**
    * Imposta un set coerente di azioni mobili per più notifiche
    * Includi azioni di *snooze* per silenziare in base a criteri
* **Snapshot di immagini** flessibili
    * Supporta telecamere, immagini MQTT e URL di immagini
    * Riposiziona le telecamere verso preimpostazioni PTZ prima e dopo uno snapshot
* Scelta del livello di configurazione
    * Imposta valori predefiniti a livello di adattatore di trasporto, consegna e azione
* Soppressione di **notifiche duplicate**
    * Regola il tempo di attesa prima di riconsentire
* **Archiviazione** delle notifiche e **supporto al debug**
    * Archivia facoltativamente le notifiche nel file system e/o su un topic MQTT
    * Include informazioni di debug complete
    * Consegne, trasporti, destinatari e scenari esposti come entità nell'interfaccia di Home Assistant


## YAML solo per uso avanzato

Supernotify supporta attualmente la configurazione standard tramite l'interfaccia di Home Assistant per l'impostazione di base, e la [configurazione YAML](https://supernotify.rhizomatics.org.uk/configuration/yaml/) per le funzionalità avanzate. Lo YAML sarà mantenuto per facilitare il lavoro con set di regole più ampi.

Molto può essere fatto con la semplice configurazione non-YAML, inclusa l'automazione della configurazione del push mobile. Consulta le [ricette](recipes/index.md) nella documentazione, e questo esempio di push mobile:

```yaml title="Con zero YAML, tutto configurato dall'interfaccia"
  - action: notify.supernotify
    data:
        message: Ciao! Test di Supernotify che invia alle app mobili di tutti
```


##  Rhizomatics Open Source per Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Attiva e disattiva automaticamente i pannelli di controllo degli allarmi di Home Assistant usando pulsanti fisici, presenza, calendari e altro
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - Acquisizione eventi OpenTelemetry (OTLP) e Syslog per Home Assistant


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integrazione con telecamere ANPR/ALPR per targhe via file system verso MQTT
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Notifica automatica via MQTT per aggiornamenti di immagini Docker

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
