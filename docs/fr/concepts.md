---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Concepts fondamentaux de Supernotify pour Home Assistant, dont Transport, Delivery, Scenario et Recipient
---
# Concepts fondamentaux

## Comment tout s'articule { #how-it-fits-together }

Une seule notification envoyée par une automatisation peut devenir plusieurs notifications différentes, chacune adaptée
au moyen par lequel elle est envoyée.

![Une notification d'une automatisation devient un e-mail, deux alertes push, un SMS et une annonce sur un haut-parleur](../assets/images/concepts_flow.svg)

1. **Cibles** - les personnes sont converties en moyens de les joindre, grâce à leurs informations de [Recipient](#recipient)
2. **Deliveries** - les [Deliveries](#delivery) concernées sont choisies, par défaut ou via des [Scenarios](#scenario)
3. **Notifications** - chaque delivery prend les cibles qu'elle peut utiliser et envoie une notification adaptée,
   ainsi un e-mail peut avoir une mise en page HTML complète avec des images, tandis que le haut-parleur de la cuisine reçoit un court message parlé

## Cible (Target) { #target }
- Qui ou quoi est notifié, et comment
  - Cibles *directes*
    - adresse e-mail
    - numéro de téléphone
    - `entity_id` ou `device_id`, par exemple pour faire une annonce sur un appareil Alexa
    - un identifiant personnalisé pour un transport spécialisé comme Telegram
  - Cibles *indirectes*, qui peuvent être converties en cibles directes
    - `person_id` pour utiliser les fonctionnalités *Recipient*
    - les sélecteurs de cible standard de Home Assistant, `label_id`, `floor_id` et `area_id`
    - cibles de *groupe* (groupes Home Assistant nouveaux comme anciens)
- Les cibles peuvent être qualifiées par une **Catégorie de cible**, comme `discord_channel:839439434` ; voir [Préfixes de catégorie](../usage/targets.md#category-prefixes)
- Chaque cible est prise dans la liste par l'intégration la plus apte à la traiter
  - Par exemple, une entité Notify d'Alexa Devices est gérée par le transport Alexa Devices, alors qu'une entité Notify générique se rabat sur le transport Notify Entity, moins complet
- Voir [Targets](../usage/targets.md) pour plus d'informations

## Destinataire (Recipient) { #recipient }
- Une personne, avec éventuellement une adresse e-mail, un numéro de téléphone, des appareils mobiles ou des cibles personnalisées
  - Par défaut, découverts automatiquement à partir des comptes utilisateurs et des entités Personne déjà présents dans Home Assistant
- Il est ainsi plus simple de désigner des personnes dans les automatisations : utilisez `person.joe_mctest` plutôt que de retenir l'adresse e-mail de Joe dans chaque notification. Fonctionne aussi pour les numéros de téléphone si une intégration SMS compatible est installée, ou pour des identifiants personnalisés comme Telegram ou Discord
- Chaque destinataire a aussi une entité `switch` Home Assistant, pour épargner facilement les notifications à quelqu'un
- Voir [People](../configuration/people.md) et [Recipes](../recipes/index.md) pour plus de détails

## Transport { #transport }

- Un *transport* est le moyen technique d'envoyer la notification, généralement via l'une des intégrations Home Assistant déjà installées
- Les *adaptateurs de transport* font toute la différence entre les groupes Notify classiques et Supernotify
  - Un groupe Notify semble permettre facilement des notifications multicanal, mais en pratique chaque transport a ses propres structures `data` (et des `data` dans les `data` !), son adressage, etc., si bien que les notifications finissent réduites au plus petit dénominateur commun, comme seulement `message` !
- Supernotify fournit d'origine des adaptateurs pour les transports courants, comme l'e-mail, le push mobile, les SMS et Alexa, ainsi qu'un adaptateur *Generic* pour encapsuler n'importe quelle autre action Home Assistant
- L'adaptateur de transport permet d'envoyer une seule notification à de nombreuses plateformes, même si leurs interfaces sont différentes et incompatibles entre elles
- Il adapte les notifications au transport, en retirant les attributs non acceptés, en remodelant les structures `data`, en ne retenant que les cibles appropriées et en permettant des réglages fins lorsque c'est possible
- Chaque transport a une configuration par défaut qui permet de nombreux réglages et valeurs par défaut, évitant de répéter les mêmes valeurs dans chaque notification
- Voir [Transports](../transports/index.md) pour plus de détails

## Envoi (Delivery) { #delivery }

- Une **Delivery** définit chaque canal de notification que vous souhaitez utiliser
  - D'origine, chaque transport a une delivery du même nom, par exemple `email` ou `mobile_push`
  - Certains transports créent automatiquement des deliveries supplémentaires, comme `alexa_devices_announce_all` ou `chime_siren_all`
  - En YAML, on peut créer d'autres deliveries, par exemple `html_email` en plus de l'`email` en texte brut, ou des deliveries distinctes pour certains assistants vocaux
- Les transports capables de sélectionner les cibles sans ambiguïté, comme l'e-mail, le push mobile, les SMS, Alexa Devices et Notify Entity, sont inclus par défaut dans le traitement des cibles
  - Les autres peuvent être inclus par configuration, via des Scenarios ou en le demandant dans une notification
- Vous pouvez définir vos propres deliveries, avec le nom de votre choix, et en avoir plusieurs pour un même transport, par exemple `plain_email` et `html_email`
- Le [transport Generic](../transports/generic.md) sert de *boîte à outils* pour créer une delivery pour presque tout ce que Home Assistant sait faire et qui n'est pas déjà couvert par un transport standard
- Voir [Deliveries](../configuration/deliveries.md) et [Recipes](../recipes/index.md) pour plus de détails

## Scénario (Scenario) { #scenario }
- Un ensemble de réglages qui peut être activé par son nom, ou automatiquement par des conditions Home Assistant
- Les scenarios peuvent être sélectionnés manuellement avec une valeur `apply_scenarios` dans le bloc `data` de la notification, ou automatiquement avec un bloc `conditions` standard de Home Assistant
  - Les conditions incluent le texte du message, si bien qu'une notification Frigate signalant des oiseaux sur la terrasse peut être traitée autrement qu'un rôdeur à une fenêtre
- Utilisez les scenarios pour rendre les notifications plus discrètes la nuit, plus festives pendant les fêtes, ou pour donner la priorité à certains messages
- Ils permettent d'appliquer des modifications en un seul endroit à de nombreuses deliveries ou notifications, et sont la clé pour simplifier radicalement les appels de notification dans vos automatisations
- Voir [Scenarios](../configuration/scenarios.md) et [Recipes](../recipes/index.md) pour plus de détails

## Priorité (Priority) { #priority }
- Un niveau d'urgence pour les notifications
   - Il n'existe pas de méthode standard pour prioriser les notifications, ni dans Home Assistant ni ailleurs
   - Supernotify a son propre schéma à 5 niveaux, qui suit les pratiques les plus courantes, de `minimum` à `critical`
   - La priorité peut servir dans les règles de scenarios et de deliveries, et être transmise aux intégrations de notification qui la prennent en charge
   - Supernotify a sa propre intégration e-mail, qui traduit la priorité dans un format compris par Outlook, Apple Mail, etc.

!!! info
    Pour les plus techniques, il existe un [Diagramme de classes](../developer/class_diagram.md) des classes principales correspondant à ces concepts.

# Principes fondamentaux { #core-principles }

1. Une notification n'a besoin que d'un message ; tout le reste peut prendre une valeur par défaut, y compris toutes les cibles
2. Ce que vous définissez dans un appel d'action prime sur les valeurs par défaut
   - Cela peut être ajusté avec des options comme `target_usage`
   - Le registre des personnes n'est utilisé pour générer des cibles que si aucune cible n'est fournie
3. Action > Scenario > Delivery > Transport pour la configuration et les valeurs par défaut
4. Aussi souple que possible dans la façon de le configurer et de l'appeler
   - Les cibles peuvent être organisées en sous-catégories, ou former une grande liste d'ID d'entités, d'ID d'appareils, d'e-mails et de numéros de téléphone
   - Les options `data` de l'action, comme `delivery`, peuvent être une valeur unique, une liste ou un dictionnaire

## Développeurs { #developers }

Voir [Developer Concepts](../developer/concepts.md) pour le cheminement des notifications à travers les deliveries, les cibles et les *Envelopes*, ainsi que les [Design Principles](../developer/principles.md).
