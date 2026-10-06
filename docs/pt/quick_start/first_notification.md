---
title: Envie sua primeira notificação
tags:
  - quickstart
  - developer tools
  - notification
description: Envie uma primeira notificação do Supernotify a partir do Home Assistant - para todos, para uma pessoa e para os alto-falantes Alexa
---
# Envie sua primeira notificação

Tudo nesta página é feito na interface do Home Assistant, logo após a [instalação](installation.md). Cada passo mostra também o YAML, para quem preferir.

## 1. Notificar todos { #1-notify-everyone }

Abra o [aba Ações](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab) nas **Ferramentas de desenvolvedor**, escolha a ação `supernotify.notify`, escreva uma mensagem e pressione **Executar ação**.

![Ação nas ferramentas de desenvolvedor](../../assets/images/tools_action_notify.png){width=600}

```yaml title="Mensagem para todos"
action: supernotify.notify
data:
  message: Something went off in the basement
```

Uma notificação só precisa de uma mensagem. Sem mais nada indicado, segue para todos os celulares e tablets com o aplicativo do Home Assistant, de todas as pessoas da casa.

## 2. Notificar uma pessoa { #2-notify-one-person }

Provavelmente são mais pessoas do que você quer. Para limitar, escolha entidades `person`, ou dispositivos móveis individuais, como **destinos** (targets):

![Notificar todos os dispositivos móveis de uma pessoa](../../assets/images/person_notify.png){width=400}

```yaml title="Mensagem para uma pessoa"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

Agora só os dispositivos do John a recebem. Escolher uma pessoa em vez de um celular faz com que a notificação continue a chegar quando o John trocar de celular.

## 3. Escolher como é enviada { #3-choose-how-its-sent }

A caixa **Delivery** lista as formas que o Supernotify encontrou para enviar notificações. Se você a deixar vazia, o Supernotify escolhe por você; se escolher algumas, só essas são usadas.

![Seleção da delivery](../../assets/images/delivery_choice.png)

Se você tiver dispositivos Alexa, use `alexa_devices_announce_all` ou `alexa_devices_speak_all`. (Announce acrescenta um toque de introdução, speak não.) Você pode combiná-las com e-mail e notificações no aplicativo móvel em uma única notificação.

```yaml title="Alto-falantes e celulares juntos"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

Cada uma recebe uma notificação adequada, por isso os alto-falantes dizem a mensagem enquanto os celulares a mostram.

Quando isso funcionar, o passo seguinte é [adicionar uma notificação a uma automação](next_steps.md#add-a-notification-to-an-automation).
