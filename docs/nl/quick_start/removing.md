---
title: Verwijderen
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Supernotify voor Home Assistant verwijderen en opruimen wat achterblijft
---

# Supernotify verwijderen

Kies in het HACS-menu `Supernotify` en kies `Verwijderen` in het menu `...`.

### Configuratie opruimen { #cleaning-up-config }

1. Handmatig aangemaakte YAML-bestanden in de map `config` blijven staan; verwijder ze zelf als je zeker weet dat je ze niet meer nodig hebt.
2. Gearchiveerde meldingen blijven staan, standaard in de map `/config/archive/supernotify`, tenzij anders ingesteld. Verwijder deze map als dat nodig is.
3. Bij gebruik van camera's of afbeeldingsbijlagen kunnen mediabestanden achterblijven, standaard in de map `/config/media/supernotify`, tenzij anders ingesteld. Verwijder deze map als dat nodig is.
4. Sjablonen kunnen achterblijven, standaard in een map `supernotify/templates` onder de configuratiemap van Home Assistant, tenzij anders ingesteld. Verwijder deze map als dat nodig is.
