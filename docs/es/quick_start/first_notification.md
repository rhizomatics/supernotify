---
title: Envía tu primera notificación
tags:
  - quickstart
  - developer tools
  - notification
description: Envía una primera notificación de Supernotify desde Home Assistant - a todos, a una persona y a los altavoces Alexa
---
# Envía tu primera notificación

Todo lo de esta página se hace desde la interfaz de Home Assistant, justo después de la [instalación](installation.md). Cada paso muestra también el YAML, para quien lo prefiera.

## 1. Notificar a todos { #1-notify-everyone }

Abre la [pestaña Acciones](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab) en **Herramientas para desarrolladores**, elige la acción `supernotify.notify`, escribe un mensaje y pulsa **Ejecutar acción**.

![Acción en las herramientas para desarrolladores](../../assets/images/tools_action_notify.png){width=600}

```yaml title="Mensaje para todos"
action: supernotify.notify
data:
  message: Something went off in the basement
```

Una notificación solo necesita un mensaje. Sin indicar nada más, llega a todos los teléfonos y tabletas con la aplicación de Home Assistant, de todas las personas de la casa.

## 2. Notificar a una persona { #2-notify-one-person }

Seguramente es más gente de la que quieres. Para limitarlo, elige entidades `person`, o dispositivos móviles concretos, como **destinos** (targets):

![Notificar a todos los dispositivos móviles de una persona](../../assets/images/person_notify.png){width=400}

```yaml title="Mensaje para una persona"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

Ahora solo lo reciben los dispositivos de John. Elegir una persona en lugar de un teléfono hace que la notificación siga llegando cuando John cambie de teléfono.

## 3. Elegir cómo se envía { #3-choose-how-its-sent }

El cuadro **Delivery** muestra las formas de enviar notificaciones que Supernotify ha encontrado. Si lo dejas vacío, Supernotify elige por ti; si eliges alguna, solo se usan esas.

![Selección de delivery](../../assets/images/delivery_choice.png)

Si tienes dispositivos Alexa, usa `alexa_devices_announce_all` o `alexa_devices_speak_all`. (Announce añade un tono de aviso previo; speak no). Puedes combinarlas con correo y notificaciones al móvil en una sola notificación.

```yaml title="Altavoces y teléfonos a la vez"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

Cada una recibe una notificación adecuada, así que los altavoces dicen el mensaje y los teléfonos lo muestran.

Cuando funcione, el siguiente paso es [añadir una notificación a una automatización](next_steps.md#add-a-notification-to-an-automation).
