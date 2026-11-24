---
title: Por que as notificações são difíceis
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Por que é difícil no Home Assistant enviar uma mesma notificação por e-mail, Telegram, push no telemóvel e SMS, com um catálogo dos diferentes estilos de ação de notificação e de como cada integração os usa
---
# Por que as notificações são difíceis no Home Assistant

Esta página explica por que enviar uma mensagem para vários canais é mais difícil do que parece no Home Assistant. É
a razão de existir o Supernotify, e pretende também ser uma contribuição para o trabalho atual do Home Assistant para
tornar as notificações mais fáceis. Descreve o Home Assistant **2026.11**, verificado no seu código-fonte. Cada versão
passa mais integrações para entidades notify, por isso algumas linhas da [tabela](#integrations-and-their-styles)
vão mudar.

## "Por que não posso simplesmente usar um grupo?" { #why-cant-i-just-use-a-group }

Imagine que um alerta deve chegar ao seu telemóvel, ao seu e-mail, a um chat de família no Telegram e, por SMS, a
alguém sem smartphone. O Home Assistant tem grupos de notificação, por isso parece natural criar um grupo com estes
quatro e enviar para ele. Há dois tipos de grupo de notificação, e nenhum consegue conter os quatro.

**O auxiliar Grupo de notificação**, criado na interface, agrupa **entidades notify** e envia com
`notify.send_message`. A Companion App, o SMTP e o bot do Telegram têm entidades notify, por isso três dos quatro
podem entrar. O SMS não: as integrações de SMS, como Twilio SMS e ClickSend, só têm o estilo antigo de ação notify. O
grupo envia apenas `message` e `title`, e retira o título para todos se algum membro não suportar títulos. Não há
forma de acrescentar uma imagem da câmara, um botão na notificação do telemóvel, um corpo de e-mail em HTML ou
qualquer outra coisa.

**O grupo notify antigo**, só em YAML, agrupa as **ações notify** antigas, como `notify.mobile_app_annas_phone` ou
`notify.smtp`. O Telegram não pode entrar, porque a sua ação notify foi removida na 2026.11 e só resta a entidade
notify. Os outros três podem, mas cada membro recebe a mesma chamada:

- `target` significa algo diferente para cada um: endereços de e-mail para o SMTP e números de telefone para o
  Twilio, enquanto a ação própria de um telemóvel o ignora. Um único `target` não pode servir a todos.
- `data` é enviado a cada membro, sejam quais forem as chaves. Uma imagem é `data.image` para a Companion App,
  `data.images` (uma lista de ficheiros locais) para o SMTP e `data.media_url` para o Twilio SMS. Cada membro recebe
  também as chaves destinadas aos outros, além das suas.
- Cada membro pode ter `data` fixos no YAML, mas não dados que mudam a cada notificação, como uma imagem para este
  alerta.

Nenhum dos tipos de grupo sabe quem está a notificar. Quando um telemóvel é substituído, é preciso editar o grupo. Se
alguém está fora, ou a mensagem só deve ir para quem está em casa, o grupo não consegue decidir. Os grupos são apenas
listas fixas de destinos.

## Por que é assim { #why-its-like-this }

Nada disto é culpa de ninguém. Em dez anos, o Home Assistant ganhou centenas de integrações de notificação, cada uma
com as necessidades do seu próprio serviço, e a parte comum das notificações sempre foi muito pequena:

- **Só `message` é comum.** `title` é comum à maioria das ações. `target` existe num estilo e não nos outros, e
  significa algo diferente em cada integração. Tudo o resto (imagens, botões, prioridade, som, HTML, anexos, ações ao
  tocar) vai para uma chave `data` livre no estilo antigo, ou para campos de uma ação própria da integração no estilo
  novo. Nenhum esquema comum os abrange.
- **A mesma ideia tem nomes diferentes.** Uma ação ao tocar é `data.url` no iOS mas `data.clickAction` no Android,
  ambas na Companion App. É `click` no ntfy e `url` no Prowl e no Pushover. A prioridade vai de `-2` a `2` no Pushover
  e no Prowl, de `1` a `5` no ntfy, é `info`/`warning`/`critical` no LaMetric, e `interruption-level` dentro de `push`
  na Companion App para iOS.
- **Alguns serviços têm uma ação por destino.** O estilo antigo da Companion App cria uma ação
  `notify.mobile_app_<device>` para cada telemóvel, por isso o nome da ação é o destino. As automações indicam o
  telemóvel, não a pessoa, e têm de ser alteradas quando o telemóvel é substituído.
- **Alguns serviços têm dois estilos ao mesmo tempo.** As integrações mais recentes oferecem uma entidade notify, que
  funciona com `notify.send_message`, áreas, etiquetas e grupos, mas só envia mensagem e título. Para tudo o resto,
  acrescentam uma ação própria dirigida à mesma entidade, como `smtp.send_message` ou `ntfy.publish`. Para usar uma
  imagem é preciso deixar a ação comum e passar para a ação própria da integração.
- **Voz, campainhas e mensagens no ecrã são outra coisa.** `tts.speak`, `persistent_notification.create`,
  `alexa_devices.send_sound` e `mqtt.publish` têm cada uma a sua forma e os seus destinos, e nenhuma é uma ação
  notify.

As entidades notify são o caminho certo: podem ser dirigidas por área, etiqueta e dispositivo, e aparecem
corretamente na interface. Mas ainda não transportam nada além de mensagem e título, e muitas integrações,
sobretudo as de SMS, ainda não passaram para elas.

## Os estilos de ação de notificação { #the-styles-of-notification-action }

### 1. Ação notify antiga para um serviço { #1-legacy-notify-action-for-a-service }

Uma ação por cada serviço configurado, com uma forma comum: `message`, `title`, `target` e um `data` livre. O
significado de `target` e as chaves de `data` pertencem a cada integração.

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

A mesma ação para o Twilio SMS aceita números de telefone como `target` e `media_url` em `data`.

### 2. Ação notify antiga para um dispositivo { #2-legacy-notify-action-for-a-device }

A mesma forma do estilo 1, mas a integração cria uma ação por dispositivo, por isso o destino está no nome da ação. O
exemplo principal é a Companion App, com `notify.mobile_app_<device>` para cada telemóvel e chaves de `data`
diferentes para iOS e Android.

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

### 3. Entidade notify com `notify.send_message` { #3-notify-entity-with-notifysend_message }

Uma ação comum a todas as entidades notify, que pode ser dirigida por entidade, dispositivo, área ou etiqueta, e é
totalmente suportada pelo editor da interface. Aceita apenas `message` e `title`, e o título só é usado pelas
entidades que declaram suportá-lo. Não há `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. A ação própria da integração, dirigida à sua entidade notify { #4-the-integrations-own-action-aimed-at-its-notify-entity }

A entidade notify da integração serve de destino, e a integração acrescenta uma ação própria com campos planos para
tudo o que `notify.send_message` não consegue enviar. Os campos diferem de integração para integração.

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

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` e as ações
`telegram_bot.send_*` funcionam da mesma forma, cada uma com campos diferentes.

### 5. A ação própria da integração, com os seus próprios destinos { #5-the-integrations-own-action-with-its-own-targets }

Ações que não se baseiam de todo em notify e escolhem o destino à sua maneira: um dispositivo, uma sala, um topic, ou
um leitor multimédia juntamente com um motor de TTS.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Outras são `lametric.message` (por `device_id`), `alexa_devices.send_sound` (por `device_id`), `matrix.send_message`
(por sala), `mqtt.publish` (por topic) e `persistent_notification.create` (sem destino, aparece na interface do
Home Assistant).

### 6. Grupos { #6-groups }

Os dois tipos de grupo de notificação estão descritos [acima](#why-cant-i-just-use-a-group). O auxiliar Grupo de
notificação é uma entidade notify usada com o estilo 3. O grupo notify antigo é uma ação do estilo 1 que chama outras
ações do estilo 1 ou 2.

## As integrações e os seus estilos { #integrations-and-their-styles }

Home Assistant 2026.11. **Ambos** significa que a integração tem dois estilos, sendo a entidade notify o mais fácil e
o outro necessário para tudo o que vá além de mensagem e título.

| Integração              | Ação antiga (1 ou 2)                     | Entidade notify (3)            | Ação própria (4 ou 5)                            | Além de mensagem e título                         |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Ambos**, por telemóvel       | -                                                | `data` antigo: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (e-mail)           | `notify.<name>`, `target` = endereços    | **Ambos**, por destinatário    | `smtp.send_message` (4)                          | Antiga `data.images`, `data.html`; ação própria `html`, `attachments`, `priority` |
| Bot do Telegram         | Removida na 2026.11                      | Sim, por chat                  | `telegram_bot.send_message`, `send_photo`, ... (4) | Ações próprias: `keyboard`, `inline_keyboard`, `parse_mode`, ações separadas para fotos e ficheiros |
| Twilio SMS              | `notify.<name>`, `target` = números      | Não                            | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = números      | Não                            | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = números      | Não                            | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = dispositivos | Não                            | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = canais       | Não                            | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = IDs de canal | **Ambos**, por canal, sem título | -                                             | Antiga `data.images`, `data.embed`, `data.urls`   |
| Matrix                  | `notify.<name>`, `target` = salas        | Não                            | `matrix.send_message` (5)                        | `data.images`                                     |
| Push HTML5              | `notify.<name>`, `target` = registos     | **Ambos**                      | `html5.send_message` (4)                         | Ação própria: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Ambos**                      | `ntfy.publish` (4)                               | Ação própria: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, obsoleta                | **Ambos**, sem título          | `prowl.send_message` (4)                         | Ação própria: `priority`, `url`                   |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Ambos**                      | `nfandroidtv.send_message` (4)                   | Ação própria: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Ambos**, sem título          | `lametric.message` por dispositivo (5)           | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | Não (proposta)                 | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | Não                            | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Ambos**, falar e anunciar por dispositivo | `alexa_devices.send_sound` por dispositivo (5) | Sons só pela ação própria             |
| Texto para voz          | `notify.<name>` (YAML `platform: tts`)   | Não                            | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Notificação persistente | `notify.persistent_notification`         | Não                            | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Sim, sem título                | `mqtt.publish` por topic (5)                     | Qualquer payload                                  |

## Notificar uma pessoa, não um dispositivo { #notifying-a-person-not-a-device }

O Home Assistant sabe quem é cada pessoa e que rastreadores de dispositivos a seguem, mas não como contactá-la. A
equipa do Home Assistant está a trabalhar nisso, após a discussão da comunidade "What the Heck?"
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), com uma
proposta na [discussão de arquitetura #1552](https://github.com/home-assistant/architecture/discussions/1552): cada
pessoa recebe uma lista das suas entidades notify, e `notify.send_message` pode ser enviado para `person.anna`. Isso
resolve o maior problema do dia a dia, substituir o telemóvel em cada automação, e torna as entidades notify a forma
natural de contactar alguém.

O Supernotify vai suportar isto o mais depressa possível depois de ser lançado, tanto enviando para uma pessoa
através das suas entidades notify associadas como permitindo que `notify.send_message` para uma pessoa passe pelo
encaminhamento próprio do Supernotify.

## O que o Supernotify faz quanto a isto { #what-supernotify-does-about-it }

O Supernotify recebe uma notificação, com um único conjunto de opções, e transforma-a na chamada certa para cada
canal:

- **Uma ação para tudo.** `supernotify.notify` recebe uma só vez a mensagem, o título, as imagens, os botões e a
  prioridade, e cada [transport](../../transports/index.md) adapta o que o seu canal suporta ao estilo, aos nomes de
  campos e aos destinos de que a sua integração precisa, seja ação antiga, entidade notify, ação própria ou TTS.
- **Pessoas, não dispositivos.** Os [recipients](../../configuration/people.md) guardam o e-mail, o número de
  telefone, o chat do Telegram, etc. de cada pessoa, e os seus telemóveis com a Companion App são encontrados
  automaticamente. Notifique `person.anna` e cada canal recebe o endereço certo. Cada recipient tem também a sua
  própria entidade notify.
- **Quem deve recebê-la.** As notificações podem ir só para quem está em casa, ou só para quem está fora, e recorrer
  a outros canais ou pessoas. Veja a receita
  [Encaminhamento por presença com alternativa](../../recipes/presence_routing_with_fallback.md).
- **Do que se trata.** Os [scenarios](../../configuration/scenarios.md) e as prioridades decidem que canais usar,
  por isso uma mensagem de baixa prioridade pode ir só para o telemóvel, enquanto uma crítica também faz tocar
  campainhas e é anunciada pelas colunas.
- **Não com demasiada frequência.** O [adiamento](../../usage/snoozing.md) e a
  [deteção de duplicados](../../configuration/dupe_detection.md) evitam que o mesmo alerta se repita.
