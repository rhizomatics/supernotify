---
title: Por qué las notificaciones son difíciles
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Por qué es difícil en Home Assistant enviar una notificación a la vez por correo electrónico, Telegram, push móvil y SMS, con un catálogo de los distintos estilos de acción de notificación y cómo los usa cada integración
---
# Por qué las notificaciones son difíciles en Home Assistant

Esta página explica por qué enviar un mensaje a varios canales es más difícil de lo que parece en Home Assistant. Es
la razón de que exista Supernotify, y también pretende ser una contribución al trabajo actual de Home Assistant para
hacer las notificaciones más fáciles. Describe Home Assistant **2026.11**, comprobado contra su código fuente. Cada
versión pasa más integraciones a entidades notify, así que algunas filas de la
[tabla](#integrations-and-their-styles) cambiarán.

## "¿Por qué no puedo usar simplemente un grupo?" { #why-cant-i-just-use-a-group }

Supongamos que quieres que un aviso llegue a tu teléfono, a tu correo, a un chat familiar de Telegram y por SMS a
alguien sin smartphone. Home Assistant tiene grupos de notificación, así que parece natural crear un grupo con esos
cuatro y enviar a él. Hay dos tipos de grupo de notificación, y ninguno puede contener los cuatro.

**El ayudante de grupo de notificación**, configurado en la interfaz, agrupa **entidades notify** y envía con
`notify.send_message`. La Companion App, SMTP y el bot de Telegram tienen entidades notify, así que tres de los cuatro
pueden entrar. El SMS no: las integraciones de SMS, como Twilio SMS y ClickSend, solo tienen el estilo antiguo de
acción notify. El grupo envía solo `message` y `title`, y quita el título para todos si algún miembro no admite
títulos. No hay forma de añadir una captura de cámara, un botón en la notificación del teléfono, un cuerpo de correo
HTML ni nada más.

**El grupo notify antiguo**, solo en YAML, agrupa las **acciones notify** antiguas, como
`notify.mobile_app_annas_phone` o `notify.smtp`. Telegram no puede entrar, porque su acción notify se eliminó en
2026.11 y solo queda la entidad notify. Los otros tres sí, pero cada miembro recibe la misma llamada:

- `target` significa algo distinto para cada uno: direcciones de correo para SMTP y números de teléfono para Twilio,
  mientras que la acción propia de un teléfono lo ignora. Un único `target` no puede ser correcto para todos.
- `data` se envía a cada miembro, tenga las claves que tenga. Una imagen es `data.image` para la Companion App,
  `data.images` (una lista de archivos locales) para SMTP y `data.media_url` para Twilio SMS. Cada miembro recibe
  también las claves pensadas para los demás, además de las suyas.
- Cada miembro puede tener `data` fijos en el YAML, pero no datos que cambien con cada notificación, como una imagen
  para este aviso concreto.

Ningún tipo de grupo sabe a quién notifica. Cuando se cambia un teléfono, hay que editar el grupo. Si alguien está
fuera, o el mensaje solo debe llegar a quien está en casa, el grupo no puede decidirlo. Los grupos son solo listas
fijas de destinos.

## Por qué es así { #why-its-like-this }

Nada de esto es culpa de nadie. Home Assistant ha incorporado cientos de integraciones de notificación en diez años,
cada una con las necesidades de su propio servicio, y la parte común de las notificaciones siempre ha sido muy pequeña:

- **Solo `message` es común.** `title` lo tienen la mayoría de las acciones. `target` existe en un estilo y no en los
  demás, y significa algo distinto en cada integración. Todo lo demás (imágenes, botones, prioridad, sonido, HTML,
  adjuntos, acciones al tocar) va bajo una clave `data` libre en el estilo antiguo, o en campos de una acción propia
  de la integración en el estilo nuevo. Ningún esquema común los cubre.
- **La misma idea tiene nombres distintos.** Una acción al tocar es `data.url` en iOS pero `data.clickAction` en
  Android, ambas en la Companion App. Es `click` en ntfy y `url` en Prowl y Pushover. La prioridad va de `-2` a `2` en
  Pushover y Prowl, de `1` a `5` en ntfy, es `info`/`warning`/`critical` en LaMetric, y `interruption-level` bajo
  `push` en la Companion App de iOS.
- **Algunos servicios tienen una acción por destino.** El estilo antiguo de la Companion App crea una acción
  `notify.mobile_app_<device>` por cada teléfono, así que el nombre de la acción es el destino. Las automatizaciones
  nombran el teléfono, no la persona, y hay que cambiarlas cuando se cambia el teléfono.
- **Algunos servicios tienen dos estilos a la vez.** Las integraciones más nuevas ofrecen una entidad notify, que
  funciona con `notify.send_message`, áreas, etiquetas y grupos, pero solo envía mensaje y título. Para todo lo demás
  añaden una acción propia dirigida a la misma entidad, como `smtp.send_message` o `ntfy.publish`. Para usar una
  imagen hay que dejar la acción común y usar la propia de la integración.
- **Voz, timbres y mensajes en pantalla van aparte.** `tts.speak`, `persistent_notification.create`,
  `alexa_devices.send_sound` y `mqtt.publish` tienen cada una su propia forma y sus propios destinos, y ninguna es una
  acción notify.

Las entidades notify son la dirección correcta: se pueden dirigir por área, etiqueta y dispositivo, y se muestran bien
en la interfaz. Pero todavía no transportan nada más que mensaje y título, y muchas integraciones, sobre todo las de
SMS, aún no se han pasado a ellas.

## Los estilos de acción de notificación { #the-styles-of-notification-action }

### 1. Acción notify antigua para un servicio { #1-legacy-notify-action-for-a-service }

Una acción por cada servicio configurado, con una forma común: `message`, `title`, `target` y un `data` libre. El
significado de `target` y las claves de `data` dependen de cada integración.

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

La misma acción para Twilio SMS toma números de teléfono como `target` y `media_url` en `data`.

### 2. Acción notify antigua para un dispositivo { #2-legacy-notify-action-for-a-device }

La misma forma que el estilo 1, pero la integración crea una acción por dispositivo, así que el destino está en el
nombre de la acción. El ejemplo principal es la Companion App, con `notify.mobile_app_<device>` para cada teléfono, y
claves de `data` distintas para iOS y Android.

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

### 3. Entidad notify con `notify.send_message` { #3-notify-entity-with-notifysend_message }

Una acción común para todas las entidades notify, que se puede dirigir por entidad, dispositivo, área o etiqueta, y
que el editor de la interfaz admite por completo. Solo toma `message` y `title`, y el título solo lo usan las
entidades que declaran admitirlo. No hay `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. La acción propia de la integración, dirigida a su entidad notify { #4-the-integrations-own-action-aimed-at-its-notify-entity }

Se usa la entidad notify de la integración como destino, y la integración añade su propia acción con campos planos
para todo lo que `notify.send_message` no puede enviar. Los campos son distintos en cada integración.

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

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` y las acciones
`telegram_bot.send_*` funcionan igual, cada una con campos distintos.

### 5. La acción propia de la integración, con sus propios destinos { #5-the-integrations-own-action-with-its-own-targets }

Acciones que no se basan en notify en absoluto y eligen su destino a su manera: un dispositivo, una sala, un topic o
un reproductor multimedia junto con un motor de TTS.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Otras son `lametric.message` (por `device_id`), `alexa_devices.send_sound` (por `device_id`), `matrix.send_message`
(por sala), `mqtt.publish` (por topic) y `persistent_notification.create` (sin destino, aparece en la interfaz de
Home Assistant).

### 6. Grupos { #6-groups }

Los dos tipos de grupo de notificación se describen [más arriba](#why-cant-i-just-use-a-group). El ayudante de grupo
de notificación es una entidad notify que se usa con el estilo 3. El grupo notify antiguo es una acción del estilo 1
que llama a otras acciones del estilo 1 o 2.

## Integraciones y sus estilos { #integrations-and-their-styles }

Home Assistant 2026.11. **Ambos** significa que la integración tiene dos estilos, donde la entidad notify es el fácil
y el otro hace falta para todo lo que vaya más allá de mensaje y título.

| Integración             | Acción antigua (1 o 2)                   | Entidad notify (3)             | Acción propia (4 o 5)                            | Más allá de mensaje y título                      |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Ambos**, por teléfono        | -                                                | `data` antiguo: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (correo)           | `notify.<name>`, `target` = direcciones  | **Ambos**, por destinatario    | `smtp.send_message` (4)                          | Antigua `data.images`, `data.html`; acción propia `html`, `attachments`, `priority` |
| Bot de Telegram         | Eliminada en 2026.11                     | Sí, por chat                   | `telegram_bot.send_message`, `send_photo`, ... (4) | Acciones propias: `keyboard`, `inline_keyboard`, `parse_mode`, acciones aparte para fotos y archivos |
| Twilio SMS              | `notify.<name>`, `target` = números      | No                             | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = números      | No                             | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = números      | No                             | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = dispositivos | No                             | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = canales      | No                             | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = IDs de canal | **Ambos**, por canal, sin título | -                                             | Antigua `data.images`, `data.embed`, `data.urls`  |
| Matrix                  | `notify.<name>`, `target` = salas        | No                             | `matrix.send_message` (5)                        | `data.images`                                     |
| Push HTML5              | `notify.<name>`, `target` = registros    | **Ambos**                      | `html5.send_message` (4)                         | Acción propia: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Ambos**                      | `ntfy.publish` (4)                               | Acción propia: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, obsoleta                | **Ambos**, sin título          | `prowl.send_message` (4)                         | Acción propia: `priority`, `url`                  |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Ambos**                      | `nfandroidtv.send_message` (4)                   | Acción propia: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Ambos**, sin título          | `lametric.message` por dispositivo (5)           | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | No (propuesta)                 | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | No                             | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Ambos**, hablar y anunciar por dispositivo | `alexa_devices.send_sound` por dispositivo (5) | Sonidos solo con la acción propia   |
| Texto a voz             | `notify.<name>` (YAML `platform: tts`)   | No                             | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Notificación persistente | `notify.persistent_notification`        | No                             | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Sí, sin título                 | `mqtt.publish` por topic (5)                     | Cualquier payload                                 |

## Notificar a una persona, no a un dispositivo { #notifying-a-person-not-a-device }

Home Assistant sabe quién es cada persona y qué rastreadores de dispositivos la siguen, pero no cómo contactarla. El
equipo de Home Assistant está trabajando en ello, tras la discusión comunitaria "What the Heck?"
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), con una
propuesta en la [discusión de arquitectura #1552](https://github.com/home-assistant/architecture/discussions/1552):
cada persona tiene una lista de sus entidades notify, y `notify.send_message` puede enviarse a `person.anna`. Eso
resuelve el mayor problema del día a día, cambiar el teléfono en cada automatización, y convierte a las entidades
notify en la forma natural de contactar con alguien.

Supernotify lo admitirá lo antes posible una vez publicado, tanto enviando a una persona a través de sus entidades
notify vinculadas como permitiendo que `notify.send_message` a una persona pase por el enrutamiento propio de
Supernotify.

## Qué hace Supernotify al respecto { #what-supernotify-does-about-it }

Supernotify toma una notificación, con un único conjunto de opciones, y la convierte en la llamada adecuada para cada
canal:

- **Una acción para todo.** `supernotify.notify` recibe una sola vez el mensaje, el título, las imágenes, los botones
  y la prioridad, y cada [transport](../../transports/index.md) adapta lo que su canal admite al estilo, los nombres
  de campo y los destinos que necesita su integración, ya sea acción antigua, entidad notify, acción propia o TTS.
- **Personas, no dispositivos.** Los [recipients](../../configuration/people.md) guardan el correo, el número de
  teléfono, el chat de Telegram, etc. de cada persona, y sus teléfonos con la Companion App se encuentran
  automáticamente. Notifica a `person.anna` y cada canal recibe la dirección correcta. Cada recipient tiene además su
  propia entidad notify.
- **Quién debe recibirla.** Las notificaciones pueden ir solo a quienes están en casa, o solo a quienes están fuera, y
  recurrir a otros canales o personas. Consulta la receta
  [Enrutamiento por presencia con alternativa](../../recipes/presence_routing_with_fallback.md).
- **De qué se trata.** Los [scenarios](../../configuration/scenarios.md) y las prioridades deciden qué canales usar,
  así que un mensaje de baja prioridad puede ir solo al teléfono, mientras que uno crítico también hace sonar timbres
  y se anuncia por los altavoces.
- **No demasiado a menudo.** La [posposición](../../usage/snoozing.md) y la
  [detección de duplicados](../../configuration/dupe_detection.md) evitan que el mismo aviso se repita.
