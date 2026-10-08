---
title: Qué hacer después
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: Qué hacer tras la primera notificación de Supernotify - notificar desde una automatización, añadir un panel, elegir a quién y qué se notifica, y encontrar ideas en las recetas
---
# Qué hacer después

Empieza por una automatización, que para eso están las notificaciones. Lo demás es opcional y se puede hacer en cualquier orden.

## Añadir una notificación a una automatización { #add-a-notification-to-an-automation }

`supernotify.notify` es una acción como cualquier otra, así que se añade a una automatización de la forma habitual. Este ejemplo envía una notificación cuando se activa un sensor de movimiento en el pasillo.

Crea una automatización con el sensor de movimiento como desencadenante, luego elige **Añadir acción** y busca Supernotify:

![Seleccionar la acción](../../assets/images/add_action_automation.png){width=600}

Rellena el mensaje y cualquier otra cosa que quieras de [tu primera notificación](first_notification.md), como un destino o una delivery:

![Configurar la acción](../../assets/images/automation_action_simple.png){width=600}

```yaml title="Automatización con sensor de movimiento"
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

Para oírla también por los altavoces, añade `alexa_devices_announce_all` y `mobile_push` como deliveries. [Enviar notificaciones](../../usage/notifying.md) explica todo lo demás que puede hacer la acción.

Para un ejemplo más completo, con anuncios por voz y una imagen de la cámara, consulta la receta [Hay alguien en la puerta](../../recipes/someone_at_the_door.md).

## Añadir un panel { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) ofrece muchas tarjetas específicas para controlar y supervisar las notificaciones, enviarlas a mano o probar configuraciones.

![Tarjetas de resumen y de transport](../../assets/images/cards.png)

La página [Dashboard](../../configuration/dashboard.md) tiene un ejemplo completo para pegar en un panel nuevo, que después se puede editar de forma visual.

## Activar y desactivar personas y deliveries { #switch-people-and-deliveries-on-and-off }

Cada persona que Supernotify conoce tiene una entidad `switch` en Home Assistant, y cada delivery también. Apaga una para que no se moleste a alguien, o para silenciar los altavoces un rato, sin cambiar ninguna automatización.

## Notificar solo a algunos dispositivos { #notify-just-some-devices }

Los destinos pueden ser un **Área**, una **Planta** o una **Etiqueta**, además de una persona o un dispositivo, así que una notificación puede ir a los altavoces de la planta baja o a todo lo etiquetado para la cocina. Consulta [Targets](../../usage/targets.md) y las [preguntas frecuentes](../../faqs.md).

## Ajustar la configuración { #tune-the-settings }

El archivado, la detección de duplicados y el mantenimiento se pueden cambiar desde la opción **Configurar** de la integración, en **Ajustes → Dispositivos y servicios**. Consulta [Archivado](../../configuration/archiving.md) y [Detección de duplicados](../../configuration/dupe_detection.md).

## Inspírate { #be-inspired }

Encontrarás muchas ideas con configuración de ejemplo en las [recetas](../../recipes/index.md).

## Ir más lejos con YAML { #go-further-with-yaml }

Con algo de configuración YAML se puede hacer más, y todo es opcional:

- Dar a las personas una dirección de correo o un número de teléfono, en [People](../../configuration/people.md)
- Crear tus propias deliveries, como un correo HTML o un grupo fijo de altavoces, en [Deliveries](../../configuration/deliveries.md)
- Cambiar cómo se comportan las notificaciones por la noche, o cuando no hay nadie en casa, con [Scenarios](../../configuration/scenarios.md)
- Adjuntar capturas de cámara, en [Multimedia](../../configuration/multimedia.md)

[Conceptos avanzados](advanced_concepts.md) explica las ideas que hay detrás, y [Configuración](../../configuration/index.md) es la referencia.

## Obtener ayuda { #get-help }

Pregunta en la página de [Discussions](https://github.com/rhizomatics/supernotify/discussions), o usa un agente de IA - mira la última respuesta de las [preguntas frecuentes](../../faqs.md).
