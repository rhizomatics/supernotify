---
title: Désinstallation
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Désinstaller Supernotify pour Home Assistant et nettoyer ce qui reste
---

# Désinstaller Supernotify

Dans le menu HACS, sélectionnez `Supernotify` et choisissez `Supprimer` dans le menu `...`.

### Nettoyer la configuration { #cleaning-up-config }

1. Les fichiers YAML créés à la main dans le répertoire `config` ne sont pas touchés ; supprimez-les vous-même si vous êtes sûr de ne plus en avoir besoin.
2. Les notifications archivées sont conservées, par défaut dans le répertoire `/config/archive/supernotify`, sauf configuration contraire. Supprimez ce répertoire si nécessaire.
3. Si vous utilisez des caméras ou des images jointes, des fichiers multimédias peuvent rester, par défaut dans le répertoire `/config/media/supernotify`, sauf configuration contraire. Supprimez ce répertoire si nécessaire.
4. Des modèles peuvent rester, par défaut dans un répertoire `supernotify/templates` sous le répertoire de configuration de Home Assistant, sauf configuration contraire. Supprimez ce répertoire si nécessaire.
