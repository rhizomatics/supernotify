---
title: Désinstallation
tags:
  - installation
  - marketplace
  - configuration
  - quickstart
description: Désinstaller Supernotify pour Home Assistant et nettoyer ce qui reste
---

# Désinstaller Supernotify

Allez dans **Paramètres → Marketplace**, ouvrez **Supernotify** et choisissez **Désinstaller** dans le menu à trois points. Il ne peut pas être désinstallé tant qu'il est encore configuré : supprimez-le d'abord dans **Paramètres → Appareils et services**, ou choisissez **Supprimer et désinstaller**, qui supprime aussi ses appareils et entités.

Avant Home Assistant 2026.11 : Dans le menu HACS, sélectionnez `Supernotify` et choisissez `Supprimer` dans le menu `...`.

### Nettoyer la configuration { #cleaning-up-config }

1. Les fichiers YAML créés à la main dans le répertoire `config` ne sont pas touchés ; supprimez-les vous-même si vous êtes sûr de ne plus en avoir besoin.
2. Les notifications archivées sont conservées, par défaut dans le répertoire `/config/archive/supernotify`, sauf configuration contraire. Supprimez ce répertoire si nécessaire.
3. Si vous utilisez des caméras ou des images jointes, des fichiers multimédias peuvent rester, par défaut dans le répertoire `/config/media/supernotify`, sauf configuration contraire. Supprimez ce répertoire si nécessaire.
4. Des modèles peuvent rester, par défaut dans un répertoire `supernotify/templates` sous le répertoire de configuration de Home Assistant, sauf configuration contraire. Supprimez ce répertoire si nécessaire.
