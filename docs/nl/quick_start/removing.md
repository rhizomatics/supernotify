---
title: Verwijderen
tags:
  - installation
  - marketplace
  - configuration
  - quickstart
description: Supernotify voor Home Assistant verwijderen en opruimen wat achterblijft
---

# Supernotify verwijderen

Ga naar **Instellingen → Marketplace**, open **Supernotify** en kies **Deïnstalleren** in het menu met de drie puntjes. Zolang het nog is ingesteld, kan het niet worden gedeïnstalleerd, dus verwijder het eerst via **Instellingen → Apparaten & diensten**, of kies **Verwijderen en deïnstalleren**, wat ook de apparaten en entiteiten ervan verwijdert.

Vóór Home Assistant 2026.11: Kies in het HACS-menu `Supernotify` en kies `Verwijderen` in het menu `...`.

### Configuratie opruimen { #cleaning-up-config }

1. Handmatig aangemaakte YAML-bestanden in de map `config` blijven staan; verwijder ze zelf als je zeker weet dat je ze niet meer nodig hebt.
2. Gearchiveerde meldingen blijven staan, standaard in de map `/config/archive/supernotify`, tenzij anders ingesteld. Verwijder deze map als dat nodig is.
3. Bij gebruik van camera's of afbeeldingsbijlagen kunnen mediabestanden achterblijven, standaard in de map `/config/media/supernotify`, tenzij anders ingesteld. Verwijder deze map als dat nodig is.
4. Sjablonen kunnen achterblijven, standaard in een map `supernotify/templates` onder de configuratiemap van Home Assistant, tenzij anders ingesteld. Verwijder deze map als dat nodig is.
