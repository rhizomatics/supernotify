---
title: Installazione
tags:
  - installation
  - marketplace
  - hacs
  - configuration
  - quickstart
description: Installa Supernotify per Home Assistant dal Marketplace, o da HACS prima della 2026.11, e configuralo dall'interfaccia, senza YAML
---

# Installazione

## Installare dal Marketplace { #install-from-the-marketplace }

Da Home Assistant 2026.11, vai in **Impostazioni → Marketplace**, cerca **Supernotify** e aprilo, oppure vai direttamente con questo pulsante:

[![Apri nel Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=rhizomatics&repository=supernotify&category=integration)

Seleziona **Installa** e di nuovo **Installa** per confermare. Supernotify è nel catalogo del Marketplace, quindi non serve aggiungere un repository personalizzato. Se Home Assistant deve essere riavviato, una riparazione in **Impostazioni → Sistema → Riparazioni** offre di farlo. Maggiori dettagli nella [documentazione del Marketplace](https://www.home-assistant.io/integrations/marketplace).

## Installare da HACS { #install-from-hacs }

Prima di Home Assistant 2026.11, il Marketplace era l'integrazione separata **HACS**, quindi per prima cosa assicurati di avere **HACS** installato.

In caso contrario, consulta le [istruzioni di HACS](https://hacs.xyz/docs/use/). Supernotify è uno dei repository predefiniti di HACS, quindi non serve configurare un repository personalizzato.

Nella pagina HACS di Home Assistant, seleziona **Supernotify** nell'elenco delle integrazioni disponibili, scaricalo e riavvia Home Assistant.

![Selezione in HACS](../../assets/images/hacs_select.png){width=400}

## Aggiungere l'integrazione { #add-the-integration }

Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e cerca **Supernotify**. Accetta i valori predefiniti.

![Aggiunta dell'integrazione](../../assets/images/new_integration.png)

## Rilevamento e valori predefiniti { #discovery-and-defaults }

Questo è tutto ciò che serve per far funzionare le prime notifiche.

Supernotify guarda cosa c'è già in Home Assistant e trova:

- **Persone** - chiunque abbia una *Persona* o un *Utente* in Home Assistant, con i telefoni e i tablet su cui usa l'app di Home Assistant
- **Modi per notificare** - notifiche push sul cellulare, un'integrazione e-mail SMTP esistente, tutte le entità notify e dispositivi come altoparlanti Alexa o campanelli, se li hai

Crea una *delivery* per ogni modo di notificare che trova, più alcune di comodo, come `chime_siren_all` e `alexa_devices_announce_all`, se hai quei dispositivi.

Archivio, rilevamento dei duplicati e impostazioni di manutenzione si possono modificare in seguito dall'opzione **Configura** dell'integrazione.

Ora [invia la tua prima notifica](first_notification.md).
