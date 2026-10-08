---
title: Rimozione
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Rimuovi Supernotify per Home Assistant e ripulisci ciò che resta
---

# Rimuovere Supernotify

Dal menu di HACS, seleziona `Supernotify` e scegli `Rimuovi` dal menu `...`.

### Ripulire la configurazione { #cleaning-up-config }

1. I file YAML creati a mano nella directory `config` non vengono toccati; rimuovili tu se sei sicuro che non serviranno più.
2. Le notifiche archiviate restano, per impostazione predefinita nella directory `/config/archive/supernotify`, salvo diversa configurazione. Rimuovi questa directory se necessario.
3. Se usi telecamere o immagini allegate, possono restare file multimediali, per impostazione predefinita nella directory `/config/media/supernotify`, salvo diversa configurazione. Rimuovi questa directory se necessario.
4. Possono restare dei template, per impostazione predefinita in una directory `supernotify/templates` sotto la directory di configurazione di Home Assistant, salvo diversa configurazione. Rimuovi questa directory se necessario.
