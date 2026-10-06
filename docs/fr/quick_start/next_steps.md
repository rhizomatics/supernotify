---
title: Que faire ensuite
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: Que faire après une première notification Supernotify - notifier depuis une automatisation, ajouter un tableau de bord, choisir qui et quoi est notifié, et trouver des idées dans les recettes
---
# Que faire ensuite

Commencez par une automatisation, puisque c'est à cela que servent les notifications. Le reste est facultatif et peut se faire dans n'importe quel ordre.

## Ajouter une notification à une automatisation { #add-a-notification-to-an-automation }

`supernotify.notify` est une action comme une autre, elle s'ajoute donc à une automatisation de la manière habituelle. Cet exemple envoie une notification quand un détecteur de mouvement se déclenche dans le couloir.

Créez une automatisation avec le détecteur de mouvement comme déclencheur, puis choisissez **Ajouter une action** et cherchez Supernotify :

![Sélection de l'action](../../assets/images/add_action_automation.png){width=600}

Renseignez le message, et tout ce que vous voulez reprendre de [votre première notification](first_notification.md), comme une cible ou une delivery :

![Configuration de l'action](../../assets/images/automation_action_simple.png){width=600}

```yaml title="Automatisation avec détecteur de mouvement"
alias: Hallway motion notification
triggers:
  - trigger: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
actions:
  - action: supernotify.notify
    data:
      title: Motion detected
      message: Something is moving in the hallway
      target: person.john_mcdoe
```

Pour l'entendre aussi sur les enceintes, ajoutez `alexa_devices_announce_all` et `mobile_push` comme deliveries. [Envoyer des notifications](../../usage/notifying.md) décrit tout ce que l'action sait faire d'autre.

Pour un exemple plus complet, avec annonces vocales et image de caméra, voyez la recette [Quelqu'un est à la porte](../../recipes/someone_at_the_door.md).

## Ajouter un tableau de bord { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) propose de nombreuses cartes dédiées pour contrôler et surveiller les notifications, en envoyer à la main ou tester des configurations.

![Cartes de vue d'ensemble et de transport](../../assets/images/cards.png)

La page [Dashboard](../../configuration/dashboard.md) contient un exemple complet à coller dans un nouveau tableau de bord, qui peut ensuite être modifié visuellement.

## Activer et désactiver des personnes et des deliveries { #switch-people-and-deliveries-on-and-off }

Chaque personne connue de Supernotify a une entité `switch` dans Home Assistant, et chaque delivery aussi. Éteignez-en une pour ne plus déranger quelqu'un, ou pour faire taire les enceintes un moment, sans modifier aucune automatisation.

## Notifier seulement certains appareils { #notify-just-some-devices }

Une cible peut être une **Zone**, un **Étage** ou une **Étiquette**, en plus d'une personne ou d'un appareil. Une notification peut ainsi aller aux enceintes du rez-de-chaussée, ou à tout ce qui porte l'étiquette de la cuisine. Voir [Targets](../../usage/targets.md) et la [FAQ](../../faqs.md) pour les questions courantes.

## Ajuster les réglages { #tune-the-settings }

L'archivage, la détection des doublons et la maintenance se modifient depuis l'option **Configurer** de l'intégration, dans **Paramètres → Appareils et services**. Voir [Archivage](../../configuration/archiving.md) et [Détection des doublons](../../configuration/dupe_detection.md).

## Trouver l'inspiration { #be-inspired }

Vous trouverez de nombreuses idées, avec des exemples de configuration, dans les [recettes](../../recipes/index.md).

## Aller plus loin avec YAML { #go-further-with-yaml }

Un peu de configuration YAML permet d'aller plus loin, et tout cela est facultatif :

- Donner aux personnes une adresse e-mail ou un numéro de téléphone, dans [People](../../configuration/people.md)
- Créer vos propres deliveries, comme un e-mail HTML ou un groupe fixe d'enceintes, dans [Deliveries](../../configuration/deliveries.md)
- Changer le comportement des notifications la nuit, ou quand il n'y a personne à la maison, avec les [Scenarios](../../configuration/scenarios.md)
- Joindre des captures de caméra, dans [Multimedia](../../configuration/multimedia.md)

[Concepts avancés](advanced_concepts.md) explique les idées sous-jacentes, et [Configuration](../../configuration/index.md) est la référence.

## Obtenir de l'aide { #get-help }

Posez vos questions sur la page [Discussions](https://github.com/rhizomatics/supernotify/discussions), ou utilisez un agent IA - voir la dernière réponse de la [FAQ](../../faqs.md).
