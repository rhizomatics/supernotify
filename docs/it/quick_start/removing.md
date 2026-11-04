---
title: Rimozione
tags:
  - installation
  - marketplace
  - configuration
  - quickstart
description: Rimuovi Supernotify per Home Assistant e ripulisci ciò che resta
---

# Rimuovere Supernotify

Vai in **Impostazioni → Marketplace**, apri **Supernotify** e scegli **Disinstalla** dal menu con i tre puntini. Non si può disinstallare finché è ancora configurato, quindi rimuovilo prima da **Impostazioni → Dispositivi e servizi**, oppure scegli **Elimina e disinstalla**, che elimina anche i suoi dispositivi ed entità.

Prima di Home Assistant 2026.11: Dal menu di HACS, seleziona `Supernotify` e scegli `Rimuovi` dal menu `...`.

### Ripulire la configurazione { #cleaning-up-config }

1. I file YAML creati a mano nella directory `config` non vengono toccati; rimuovili tu se sei sicuro che non serviranno più.
2. Le notifiche archiviate restano, per impostazione predefinita nella directory `/config/archive/supernotify`, salvo diversa configurazione. Rimuovi questa directory se necessario.
3. Se usi telecamere o immagini allegate, possono restare file multimediali, per impostazione predefinita nella directory `/config/media/supernotify`, salvo diversa configurazione. Rimuovi questa directory se necessario.
4. Possono restare dei template, per impostazione predefinita in una directory `supernotify/templates` sotto la directory di configurazione di Home Assistant, salvo diversa configurazione. Rimuovi questa directory se necessario.
