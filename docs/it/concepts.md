---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Concetti fondamentali di Supernotify per Home Assistant, tra cui transport, delivery, scenario e recipient
---
# Concetti fondamentali

## Come si combina il tutto { #how-it-fits-together }

Una sola notifica da un'automazione può trasformarsi in più notifiche diverse, ognuna adattata
al modo in cui viene inviata.

![Una notifica da un'automazione diventa un'e-mail, due notifiche push, un SMS e un annuncio da un altoparlante](../assets/images/concepts_flow.svg)

1. **Destinazioni** - le persone vengono trasformate nei modi in cui possono essere raggiunte, usando i loro dati di [recipient](#recipient)
2. **Delivery** - vengono scelte le [delivery](#delivery) pertinenti, per impostazione predefinita o tramite gli [scenario](#scenario)
3. **Notifiche** - ogni delivery prende le destinazioni che può usare e invia una notifica adatta,
   così un'e-mail può avere un layout HTML completo con immagini, mentre l'altoparlante della cucina riceve un breve messaggio vocale

## Destinazione (target) { #target }
- Chi o cosa riceve la notifica, e come
  - Destinazioni *dirette*
    - indirizzo e-mail
    - numero di telefono
    - `entity_id` o `device_id`, ad esempio per fare un annuncio su un dispositivo Alexa
    - un ID personalizzato per un transport specializzato come Telegram
  - Destinazioni *indirette*, che possono essere trasformate in destinazioni dirette
    - `person_id` per usare le funzionalità dei *recipient*
    - i selettori di destinazione standard di Home Assistant, `label_id`, `floor_id` e `area_id`
    - destinazioni di *gruppo* (gruppi di Home Assistant sia nuovi che vecchi)
- Le destinazioni possono essere qualificate con una **Categoria di destinazione**, come `discord_channel:839439434`; vedi [Prefissi di categoria](../usage/targets.md#category-prefixes)
- Ogni destinazione viene presa dall'elenco dall'integrazione più adatta a gestirla
  - Ad esempio, un'entità Notify di Alexa Devices è gestita dal transport Alexa Devices, mentre un'entità Notify generica ricade sul transport Notify Entity, meno completo
- Vedi [Targets](../usage/targets.md) per maggiori informazioni

## Recipient { #recipient }
- Una persona, con indirizzo e-mail, numero di telefono, dispositivi mobili o destinazioni personalizzate facoltativi
  - Per impostazione predefinita rilevati automaticamente dagli account utente e dalle entità Persona già presenti in Home Assistant
- Rende più semplice riferirsi alle persone nelle automazioni: usa `person.joe_mctest` invece di ricordare l'e-mail di Joe in ogni notifica. Funziona anche con i numeri di telefono se è installata un'integrazione SMS compatibile, o con identificativi personalizzati come Telegram o Discord
- Ogni recipient ha anche un'entità `switch` di Home Assistant, così è facile evitare di disturbare qualcuno con le notifiche
- Vedi [People](../configuration/people.md) e [Recipes](../recipes/index.md) per maggiori dettagli

## Transport { #transport }

- Un *transport* è il mezzo tecnico con cui si notifica, di solito tramite una delle integrazioni di Home Assistant già installate
- Gli *adattatori di transport* sono ciò che distingue Supernotify dai normali gruppi Notify
  - Un gruppo Notify sembra consentire facilmente notifiche multicanale, ma in pratica ogni transport ha strutture `data` diverse (e `data` dentro `data`!), indirizzamento ecc., quindi alla fine le notifiche vengono ridotte al minimo comune denominatore, come il solo `message`!
- Supernotify include adattatori per i transport più comuni, come e-mail, push mobile, SMS e Alexa, e un adattatore *Generic* che può avvolgere qualsiasi altra azione di Home Assistant
- L'adattatore di transport permette di inviare una sola notifica a molte piattaforme, anche quando hanno interfacce diverse e incompatibili tra loro
- Adatta le notifiche al transport, eliminando gli attributi non accettati, rimodellando le strutture `data`, selezionando solo le destinazioni appropriate e consentendo ulteriori regolazioni dove possibile
- Ogni transport ha una configurazione predefinita che permette molte regolazioni e valori predefiniti, evitando di ripetere gli stessi valori in ogni notifica
- Vedi [Transports](../transports/index.md) per maggiori dettagli

## Delivery { #delivery }

- Una **delivery** definisce ogni canale di notifica che vuoi usare
  - Di serie, ogni transport ha una delivery con lo stesso nome, ad esempio `email` o `mobile_push`
  - Alcuni transport creano automaticamente delivery aggiuntive, come `alexa_devices_announce_all` o `chime_siren_all`
  - Con YAML si possono creare altre delivery, ad esempio `html_email` oltre all'`email` in testo semplice, o delivery diverse per specifici assistenti vocali
- I transport in grado di selezionare le destinazioni in modo univoco, come e-mail, push mobile, SMS, Alexa Devices e Notify Entity, sono inclusi per impostazione predefinita nella gestione delle destinazioni
  - Gli altri possono essere inclusi tramite configurazione, usando gli scenario o richiedendoli in una notifica
- Puoi definire delivery personalizzate, con il nome che preferisci, e averne più di una per un singolo transport, ad esempio `plain_email` e `html_email`
- Il [transport Generic](../transports/generic.md) funziona come una *cassetta degli attrezzi* per creare una delivery per quasi tutto ciò che Home Assistant può fare e che non è già coperto da un transport standard
- Vedi [Deliveries](../configuration/deliveries.md) e [Recipes](../recipes/index.md) per maggiori dettagli

## Scenario { #scenario }
- Un pacchetto di impostazioni che può essere attivato per nome, o automaticamente tramite condizioni di Home Assistant
- Gli scenario possono essere selezionati manualmente con un valore `apply_scenarios` nel blocco `data` della notifica, o automaticamente con un blocco `conditions` standard di Home Assistant
  - Le condizioni includono il testo del messaggio, così una notifica di Frigate su degli uccelli in terrazza può essere gestita diversamente da un intruso alla finestra
- Usa gli scenario per rendere le notifiche meno invadenti di notte, più festose durante le feste, o per dare priorità ad alcuni messaggi
- Permettono di applicare modifiche in un unico punto a molte delivery o notifiche, e sono la chiave per semplificare radicalmente le chiamate di notifica nelle automazioni
- Vedi [Scenarios](../configuration/scenarios.md) e [Recipes](../recipes/index.md) per maggiori dettagli

## Priorità (priority) { #priority }
- Un livello di urgenza per le notifiche
   - Non esiste un modo standard per dare priorità alle notifiche, né dentro né fuori Home Assistant
   - Supernotify ha un proprio schema a 5 livelli, che segue le pratiche più comuni, da `minimum` a `critical`
   - La priorità può essere usata nelle regole di scenario e delivery, e passata alle integrazioni di notifica che la supportano
   - Supernotify ha una propria integrazione e-mail, che traduce la priorità in un formato comprensibile da Outlook, Apple Mail ecc.

!!! info
    Per chi ama i dettagli tecnici, c'è un [Diagramma delle classi](../developer/class_diagram.md) delle classi principali corrispondenti a questi concetti.

# Principi fondamentali { #core-principles }

1. A una notifica basta un messaggio; tutto il resto può avere un valore predefinito, comprese tutte le destinazioni
2. Ciò che definisci in una chiamata di azione ha la precedenza sui valori predefiniti
   - Si può regolare con opzioni come `target_usage`
   - Il registro delle persone viene usato per generare destinazioni solo se non ne viene indicata nessuna
3. Azione > scenario > delivery > transport per configurazione e valori predefiniti
4. Il meno pignolo possibile su come viene configurato e chiamato
   - Le destinazioni possono essere organizzate in sottocategorie, o essere un grande elenco di ID entità, ID dispositivo, e-mail e numeri di telefono
   - Le opzioni `data` dell'azione, come `delivery`, possono essere un valore singolo, un elenco o un dizionario

## Sviluppatori { #developers }

Vedi [Developer Concepts](../developer/concepts.md) per il percorso delle notifiche attraverso delivery, destinazioni ed *Envelope*, e i [Design Principles](../developer/principles.md).
