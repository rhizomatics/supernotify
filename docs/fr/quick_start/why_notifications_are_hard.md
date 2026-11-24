---
title: Pourquoi les notifications sont difficiles
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Pourquoi il est difficile dans Home Assistant d'envoyer une même notification par e-mail, Telegram, push mobile et SMS, avec un catalogue des différents styles d'action de notification et de la façon dont chaque intégration les utilise
---
# Pourquoi les notifications sont difficiles dans Home Assistant

Cette page explique pourquoi envoyer un message sur plusieurs canaux est plus difficile qu'il n'y paraît dans
Home Assistant. C'est la raison d'être de Supernotify, et c'est aussi une contribution au travail actuel de
Home Assistant pour simplifier les notifications. Elle décrit Home Assistant **2026.11**, vérifié dans son code source.
Chaque version fait passer davantage d'intégrations aux entités notify, donc certaines lignes du
[tableau](#integrations-and-their-styles) changeront.

## « Pourquoi ne puis-je pas simplement utiliser un groupe ? » { #why-cant-i-just-use-a-group }

Imaginons qu'une alerte doive atteindre votre téléphone, votre e-mail, une discussion Telegram familiale, et par SMS
quelqu'un qui n'a pas de smartphone. Home Assistant a des groupes de notification, il semble donc naturel de créer un
groupe avec ces quatre-là et d'envoyer vers lui. Il existe deux sortes de groupe de notification, et aucune ne peut
contenir les quatre.

**L'entrée auxiliaire Groupe de notification**, créée dans l'interface, regroupe des **entités notify** et envoie
avec `notify.send_message`. La Companion App, SMTP et le bot Telegram ont des entités notify, donc trois des quatre
peuvent y entrer. Pas le SMS : les intégrations SMS, comme Twilio SMS et ClickSend, n'ont que l'ancien style d'action
notify. Le groupe n'envoie que `message` et `title`, et il retire le titre pour tous si un membre ne prend pas en
charge les titres. Impossible d'ajouter une capture de caméra, un bouton dans la notification du téléphone, un corps
d'e-mail HTML ou quoi que ce soit d'autre.

**L'ancien groupe notify**, en YAML uniquement, regroupe les anciennes **actions notify**, comme
`notify.mobile_app_annas_phone` ou `notify.smtp`. Telegram ne peut pas y entrer, car son action notify a été
supprimée dans 2026.11 et il ne reste que l'entité notify. Les trois autres le peuvent, mais chaque membre reçoit le
même appel :

- `target` signifie quelque chose de différent pour chacun : des adresses e-mail pour SMTP et des numéros de
  téléphone pour Twilio, tandis que l'action propre d'un téléphone l'ignore. Un seul `target` ne peut pas convenir à
  tous.
- `data` est envoyé à chaque membre, quelles que soient ses clés. Une image est `data.image` pour la Companion App,
  `data.images` (une liste de fichiers locaux) pour SMTP et `data.media_url` pour Twilio SMS. Chaque membre reçoit
  aussi les clés destinées aux autres, en plus des siennes.
- Chaque membre peut avoir des `data` fixes dans le YAML, mais pas des données qui changent à chaque notification,
  comme une image pour cette alerte-ci.

Aucune des deux sortes de groupe ne sait qui elle notifie. Quand un téléphone est remplacé, il faut modifier le
groupe. Si quelqu'un est absent, ou si le message ne doit aller qu'aux personnes présentes, le groupe ne peut pas en
décider. Les groupes ne sont que des listes fixes de destinations.

## Pourquoi c'est ainsi { #why-its-like-this }

Ce n'est la faute de personne. Home Assistant a accueilli des centaines d'intégrations de notification en dix ans,
chacune avec les besoins de son propre service, et la partie commune des notifications a toujours été très réduite :

- **Seul `message` est commun.** `title` est commun à la plupart des actions. `target` existe dans un style et pas
  dans les autres, et signifie quelque chose de différent dans chaque intégration. Tout le reste (images, boutons,
  priorité, son, HTML, pièces jointes, actions au toucher) va sous une clé `data` libre dans l'ancien style, ou dans
  les champs d'une action propre à l'intégration dans le nouveau style. Aucun schéma commun ne les couvre.
- **La même idée porte des noms différents.** Une action au toucher est `data.url` sous iOS mais `data.clickAction`
  sous Android, les deux dans la Companion App. C'est `click` dans ntfy et `url` dans Prowl et Pushover. La priorité
  va de `-2` à `2` dans Pushover et Prowl, de `1` à `5` dans ntfy, vaut `info`/`warning`/`critical` dans LaMetric, et
  `interruption-level` sous `push` pour la Companion App iOS.
- **Certains services ont une action par destination.** L'ancien style de la Companion App crée une action
  `notify.mobile_app_<device>` pour chaque téléphone, donc le nom de l'action est la destination. Les automatisations
  nomment le téléphone, pas la personne, et doivent être modifiées quand le téléphone est remplacé.
- **Certains services ont deux styles à la fois.** Les intégrations récentes proposent une entité notify, qui
  fonctionne avec `notify.send_message`, les pièces, les étiquettes et les groupes, mais n'envoie que le message et le
  titre. Pour tout le reste, elles ajoutent leur propre action, visant la même entité, comme `smtp.send_message` ou
  `ntfy.publish`. Pour envoyer une image, il faut quitter l'action commune pour l'action propre à l'intégration.
- **La voix, les carillons et les messages à l'écran sont encore à part.** `tts.speak`,
  `persistent_notification.create`, `alexa_devices.send_sound` et `mqtt.publish` ont chacune leur propre forme et
  leurs propres destinations, et aucune n'est une action notify.

Les entités notify sont la bonne direction : on peut les cibler par pièce, étiquette et appareil, et elles
s'affichent correctement dans l'interface. Mais elles ne transportent encore rien d'autre que le message et le titre,
et beaucoup d'intégrations, surtout pour le SMS, n'y sont pas encore passées.

## Les styles d'action de notification { #the-styles-of-notification-action }

### 1. Ancienne action notify pour un service { #1-legacy-notify-action-for-a-service }

Une action par service configuré, avec une forme commune : `message`, `title`, `target` et un `data` libre. Le sens de
`target` et les clés de `data` sont propres à chaque intégration.

```yaml
action: notify.smtp
data:
  title: Front door
  message: The front door has been open for 10 minutes
  target:
    - anna@example.com
  data:
    images:
      - /config/www/snapshots/front_door.jpg
```

La même action pour Twilio SMS prend des numéros de téléphone comme `target` et `media_url` dans `data`.

### 2. Ancienne action notify pour un appareil { #2-legacy-notify-action-for-a-device }

Même forme que le style 1, mais l'intégration crée une action par appareil, donc la destination est dans le nom de
l'action. L'exemple principal est la Companion App, avec `notify.mobile_app_<device>` pour chaque téléphone, et des
clés `data` différentes pour iOS et Android.

```yaml
action: notify.mobile_app_annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
  data:
    image: /api/camera_proxy/camera.front_door
    url: /lovelace/doors          # iOS
    clickAction: /lovelace/doors  # Android
    actions:
      - action: CLOSE_DOOR
        title: Close it
```

### 3. Entité notify avec `notify.send_message` { #3-notify-entity-with-notifysend_message }

Une action commune à toutes les entités notify, que l'on peut cibler par entité, appareil, pièce ou étiquette, et
entièrement prise en charge par l'éditeur de l'interface. Elle ne prend que `message` et `title`, et le titre n'est
utilisé que par les entités qui déclarent le prendre en charge. Il n'y a pas de `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. L'action propre à l'intégration, visant son entité notify { #4-the-integrations-own-action-aimed-at-its-notify-entity }

L'entité notify de l'intégration sert de destination, et l'intégration ajoute sa propre action, avec des champs à plat
pour tout ce que `notify.send_message` ne peut pas envoyer. Les champs diffèrent d'une intégration à l'autre.

```yaml
action: ntfy.publish
target:
  entity_id: notify.ntfy_alerts
data:
  title: Front door
  message: The front door has been open for 10 minutes
  priority: 4
  click: https://my.home/lovelace/doors
  attach: https://my.home/local/snapshots/front_door.jpg
```

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` et les actions
`telegram_bot.send_*` fonctionnent de la même façon, chacune avec des champs différents.

### 5. L'action propre à l'intégration, avec ses propres destinations { #5-the-integrations-own-action-with-its-own-targets }

Des actions qui ne reposent pas du tout sur notify et choisissent leur destination à leur manière : un appareil, un
salon, un topic, ou un lecteur multimédia associé à un moteur TTS.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Les autres sont `lametric.message` (par `device_id`), `alexa_devices.send_sound` (par `device_id`),
`matrix.send_message` (par salon), `mqtt.publish` (par topic) et `persistent_notification.create` (sans destination,
elle apparaît dans l'interface de Home Assistant).

### 6. Groupes { #6-groups }

Les deux sortes de groupe de notification sont décrites [plus haut](#why-cant-i-just-use-a-group). L'entrée
auxiliaire Groupe de notification est une entité notify utilisée avec le style 3. L'ancien groupe notify est une
action du style 1 qui appelle d'autres actions du style 1 ou 2.

## Les intégrations et leurs styles { #integrations-and-their-styles }

Home Assistant 2026.11. **Les deux** signifie que l'intégration a deux styles, l'entité notify étant le plus simple et
l'autre étant nécessaire pour tout ce qui dépasse le message et le titre.

| Intégration             | Ancienne action (1 ou 2)                 | Entité notify (3)              | Action propre (4 ou 5)                           | Au-delà du message et du titre                    |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Les deux**, par téléphone    | -                                                | Ancien `data` : `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (e-mail)           | `notify.<name>`, `target` = adresses     | **Les deux**, par destinataire | `smtp.send_message` (4)                          | Ancienne `data.images`, `data.html` ; action propre `html`, `attachments`, `priority` |
| Bot Telegram            | Supprimée dans 2026.11                   | Oui, par discussion            | `telegram_bot.send_message`, `send_photo`, ... (4) | Actions propres : `keyboard`, `inline_keyboard`, `parse_mode`, actions séparées pour photos et fichiers |
| Twilio SMS              | `notify.<name>`, `target` = numéros      | Non                            | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = numéros      | Non                            | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = numéros      | Non                            | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = appareils    | Non                            | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = canaux       | Non                            | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = ID de salon | **Les deux**, par salon, sans titre | -                                           | Ancienne `data.images`, `data.embed`, `data.urls` |
| Matrix                  | `notify.<name>`, `target` = salons       | Non                            | `matrix.send_message` (5)                        | `data.images`                                     |
| Push HTML5              | `notify.<name>`, `target` = inscriptions | **Les deux**                   | `html5.send_message` (4)                         | Action propre : `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Les deux**                   | `ntfy.publish` (4)                               | Action propre : `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, obsolète                | **Les deux**, sans titre       | `prowl.send_message` (4)                         | Action propre : `priority`, `url`                 |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Les deux**                   | `nfandroidtv.send_message` (4)                   | Action propre : `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Les deux**, sans titre       | `lametric.message` par appareil (5)              | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | Non (proposée)                 | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | Non                            | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Les deux**, parler et annoncer par appareil | `alexa_devices.send_sound` par appareil (5) | Sons uniquement via l'action propre    |
| Synthèse vocale         | `notify.<name>` (YAML `platform: tts`)   | Non                            | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Notification persistante | `notify.persistent_notification`        | Non                            | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Oui, sans titre                | `mqtt.publish` par topic (5)                     | N'importe quel payload                            |

## Notifier une personne, pas un appareil { #notifying-a-person-not-a-device }

Home Assistant sait qui est chaque personne et quels traceurs d'appareils la suivent, mais pas comment la joindre.
L'équipe de Home Assistant y travaille, à la suite de la discussion communautaire « What the Heck? »
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), avec une
proposition dans la [discussion d'architecture #1552](https://github.com/home-assistant/architecture/discussions/1552) :
chaque personne reçoit une liste de ses entités notify, et `notify.send_message` peut être envoyé à `person.anna`.
Cela règle le plus gros problème du quotidien, remplacer le téléphone dans chaque automatisation, et fait des entités
notify le moyen naturel de joindre quelqu'un.

Supernotify prendra cela en charge dès que possible une fois publié, à la fois en envoyant à une personne via ses
entités notify liées et en permettant à `notify.send_message` vers une personne de passer par le routage propre de
Supernotify.

## Ce que fait Supernotify { #what-supernotify-does-about-it }

Supernotify prend une notification, avec un seul jeu d'options, et la transforme en l'appel adapté à chaque canal :

- **Une action pour tout.** `supernotify.notify` reçoit une seule fois le message, le titre, les images, les boutons
  et la priorité, et chaque [transport](../../transports/index.md) adapte ce que son canal prend en charge au style,
  aux noms de champs et aux destinations dont son intégration a besoin, qu'il s'agisse d'une ancienne action, d'une
  entité notify, d'une action propre ou de TTS.
- **Des personnes, pas des appareils.** Les [recipients](../../configuration/people.md) contiennent l'e-mail, le
  numéro de téléphone, la discussion Telegram, etc. de chaque personne, et leurs téléphones avec la Companion App sont
  trouvés automatiquement. Notifiez `person.anna` et chaque canal reçoit la bonne adresse. Chaque recipient a aussi sa
  propre entité notify.
- **Qui doit la recevoir.** Les notifications peuvent n'aller qu'aux personnes présentes, ou qu'aux absents, et se
  rabattre sur d'autres canaux ou d'autres personnes. Voir la recette
  [Routage selon la présence avec repli](../../recipes/presence_routing_with_fallback.md).
- **De quoi il s'agit.** Les [scenarios](../../configuration/scenarios.md) et les priorités décident des canaux à
  utiliser : un message de faible priorité peut n'aller qu'au téléphone, tandis qu'un message critique fait aussi
  sonner les carillons et est annoncé sur les haut-parleurs.
- **Pas trop souvent.** La [mise en sourdine](../../usage/snoozing.md) et la
  [détection des doublons](../../configuration/dupe_detection.md) empêchent la même alerte de se répéter.
