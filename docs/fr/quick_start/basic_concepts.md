---
title: Concepts de base
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: Les quelques concepts de Supernotify nécessaires pour démarrer - cibles, recipients, deliveries et priorité, et comment ils s'articulent
---
# Concepts de base

## Comment tout s'articule { #how-it-fits-together }

Une seule notification issue d'une automatisation peut devenir plusieurs notifications différentes, chacune adaptée à la façon dont elle est envoyée.

![Une notification issue d'une automatisation devient un e-mail, deux alertes push, un SMS et une annonce sur une enceinte](../../assets/images/concepts_flow.svg)

En lisant l'image de gauche à droite :

1. **Qui notifier** - les [cibles](#target). Les personnes sont converties en moyens de les joindre, à partir de leurs informations de [recipient](#recipient)
2. **Delivery** - les [deliveries](#delivery) concernées sont choisies, par défaut ou parce que vous les avez demandées
3. **Notifications** - chaque delivery prend les cibles qu'elle peut utiliser et envoie une notification adaptée, si bien qu'un e-mail peut avoir une mise en page HTML complète avec des images, tandis que l'enceinte de la cuisine reçoit un court message vocal

Trois mots couvrent presque tout dans une installation faite uniquement depuis l'interface.

## Cible (target) { #target }

Une cible, c'est **qui ou quoi est notifié** : une personne, un téléphone, une enceinte, une adresse e-mail, ou bien une zone, un étage ou une étiquette qui représente plusieurs appareils.

Sans cible, la notification part vers tout le monde.

## Recipient { #recipient }

Un recipient est **une personne, telle que Supernotify la connaît** : ses téléphones et tablettes et, éventuellement, une adresse e-mail et un numéro de téléphone. Les recipients sont trouvés automatiquement à partir des entités *Person* de Home Assistant.

Un recipient n'est pas un autre type de cible. Une personne est l'une des choses qu'une cible peut être, et le recipient est l'endroit où Supernotify cherche comment la joindre. C'est pourquoi `person.joe_mctest` fonctionne comme cible, sans avoir à répéter l'adresse e-mail de Joe dans chaque automatisation.

## Delivery { #delivery }

Une delivery est **un moyen d'envoyer une notification**, avec un nom, comme `mobile_push`, `email` ou `alexa_devices_announce_all`. Supernotify crée des deliveries pour tout ce qu'il trouve dans votre Home Assistant, et ce sont elles qui apparaissent dans le champ **Delivery** de l'action `supernotify.notify`.

Sans delivery précisée, Supernotify utilise celles qui savent déterminer seules où envoyer, comme les notifications push mobiles et l'e-mail.

## Priorité { #priority }

La priorité indique **à quel point une notification est urgente**, sur cinq niveaux : `minimum`, `low`, `medium`, `high` et `critical`. Elle est facultative et vaut `medium` par défaut. La priorité est transmise aux téléphones, aux logiciels de messagerie et à tout ce qui sait l'interpréter.

## Deux autres, pour plus tard { #two-more-for-later }

Ils reviennent partout dans la documentation, et aucun n'est nécessaire pour démarrer.

- Un **transport** est le moyen technique derrière une delivery, généralement une intégration Home Assistant comme l'application mobile, SMTP ou Alexa Devices. Une delivery est un transport accompagné de ses réglages, si bien qu'un transport peut avoir plusieurs deliveries, par exemple un `email` simple et un `html_email`.
- Un **scenario** est un ensemble de réglages portant un nom, qui change les deliveries utilisées et leur comportement, par exemple plus discrètes la nuit. Les scenarios se configurent en YAML.

[Concepts avancés](advanced_concepts.md) traite les deux, ainsi que tout ce que permet la configuration YAML.
