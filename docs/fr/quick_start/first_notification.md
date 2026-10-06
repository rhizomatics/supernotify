---
title: Envoyer votre première notification
tags:
  - quickstart
  - developer tools
  - notification
description: Envoyer une première notification Supernotify depuis Home Assistant - à tout le monde, à une personne et aux enceintes Alexa
---
# Envoyer votre première notification

Tout ce qui suit se fait depuis l'interface de Home Assistant, juste après l'[installation](installation.md). Chaque étape montre aussi le YAML, pour ceux qui le préfèrent.

## 1. Notifier tout le monde { #1-notify-everyone }

Ouvrez l'[onglet Actions](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab) dans les **Outils de développement**, choisissez l'action `supernotify.notify`, saisissez un message et appuyez sur **Exécuter l'action**.

![Action dans les outils de développement](../../assets/images/tools_action_notify.png){width=600}

```yaml title="Message pour tout le monde"
action: supernotify.notify
data:
  message: Something went off in the basement
```

Une notification n'a besoin que d'un message. Sans autre précision, elle part vers tous les téléphones et tablettes qui utilisent l'application Home Assistant, pour tous les habitants de la maison.

## 2. Notifier une seule personne { #2-notify-one-person }

C'est sans doute plus de monde que vous ne le souhaitez. Pour limiter, choisissez des entités `person`, ou des appareils mobiles précis, comme **cibles** (targets) :

![Notifier tous les appareils mobiles d'une personne](../../assets/images/person_notify.png){width=400}

```yaml title="Message pour une personne"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

Désormais, seuls les appareils de John la reçoivent. Choisir une personne plutôt qu'un téléphone permet à la notification d'arriver encore quand John change de téléphone.

## 3. Choisir le mode d'envoi { #3-choose-how-its-sent }

Le champ **Delivery** liste les moyens d'envoi que Supernotify a trouvés. Laissez-le vide et Supernotify choisit pour vous ; choisissez-en, et seuls ceux-là sont utilisés.

![Sélection de la delivery](../../assets/images/delivery_choice.png)

Si vous avez des appareils Alexa, utilisez `alexa_devices_announce_all` ou `alexa_devices_speak_all`. (Announce ajoute un carillon d'introduction, speak non.) Vous pouvez les combiner avec l'e-mail et les notifications mobiles dans une seule notification.

```yaml title="Enceintes et téléphones ensemble"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

Chacun reçoit une notification qui lui convient : les enceintes disent le message, les téléphones l'affichent.

Une fois que cela fonctionne, l'étape suivante est d'[ajouter une notification à une automatisation](next_steps.md#add-a-notification-to-an-automation).
