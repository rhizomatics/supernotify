---
title: Conceptos básicos
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: Los pocos conceptos de Supernotify necesarios para empezar - destinos, recipients, deliveries y prioridad, y cómo encajan entre sí
---
# Conceptos básicos

## Cómo encaja todo { #how-it-fits-together }

Una sola notificación de una automatización puede convertirse en varias notificaciones distintas, cada una adaptada a la forma en que se envía.

![Una notificación de una automatización se convierte en un correo, dos avisos push, un SMS y un anuncio por altavoz](../../assets/images/concepts_flow.svg)

Leyendo la imagen de izquierda a derecha:

1. **A quién notificar** - los [destinos](#target). Las personas se convierten en las formas de contactar con ellas, usando sus datos de [recipient](#recipient)
2. **Delivery** - se eligen las [deliveries](#delivery) que corresponden, por defecto o porque las has pedido
3. **Notificaciones** - cada delivery toma los destinos que puede usar y envía una notificación adecuada, de modo que un correo puede tener un diseño HTML completo con imágenes, mientras que el altavoz de la cocina recibe un breve mensaje hablado

Tres palabras cubren casi todo en una instalación hecha solo desde la interfaz.

## Destino (target) { #target }

Un destino es **a quién o a qué se notifica**: una persona, un teléfono, un altavoz, una dirección de correo, o un área, una planta o una etiqueta que representa varios dispositivos.

Si no indicas destinos, la notificación llega a todos.

## Recipient { #recipient }

Un recipient es **una persona, tal como la conoce Supernotify**: sus teléfonos y tabletas y, opcionalmente, una dirección de correo y un número de teléfono. Los recipients se detectan automáticamente a partir de las entidades *Person* de Home Assistant.

Un recipient no es otro tipo de destino. Una persona es una de las cosas que puede ser un destino, y el recipient es donde Supernotify consulta cómo contactar con ella. Por eso `person.joe_mctest` funciona como destino, y no necesitas la dirección de correo de Joe en cada automatización.

## Delivery { #delivery }

Una delivery es **una forma de enviar una notificación**, con un nombre, como `mobile_push`, `email` o `alexa_devices_announce_all`. Supernotify crea deliveries para lo que encuentra en tu Home Assistant, y son lo que aparece en el cuadro **Delivery** de la acción `supernotify.notify`.

Si no indicas deliveries, Supernotify usa las que pueden averiguar por sí mismas adónde enviar, como las notificaciones push y el correo.

## Prioridad { #priority }

La prioridad es **lo urgente que es una notificación**, en cinco niveles: `minimum`, `low`, `medium`, `high` y `critical`. Es opcional, y vale `medium` si no se indica. La prioridad se pasa a los teléfonos, programas de correo y demás cosas que la entienden.

## Dos más, para más adelante { #two-more-for-later }

Aparecen por toda la documentación, y ninguno hace falta para empezar.

- Un **transport** es el medio técnico que hay detrás de una delivery, normalmente una integración de Home Assistant como la aplicación móvil, SMTP o Alexa Devices. Una delivery es un transport más los ajustes con los que se usa, así que un transport puede tener varias deliveries, como un `email` sencillo y un `html_email`.
- Un **scenario** es un paquete de ajustes con nombre, que cambia qué deliveries se usan y cómo se comportan, por ejemplo más discretas por la noche. Los scenarios se configuran en YAML.

[Conceptos avanzados](advanced_concepts.md) trata ambos, y el resto de lo que permite la configuración YAML.
