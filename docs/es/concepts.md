---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Conceptos fundamentales de Supernotify para Home Assistant, incluyendo Transport, Delivery, Scenario y Recipient
---
# Conceptos fundamentales

## Cómo encaja todo { #how-it-fits-together }

Una sola notificación de una automatización puede convertirse en varias notificaciones distintas, cada una adaptada
a la forma en que se envía.

![Una notificación de una automatización se convierte en un correo electrónico, dos alertas push, un SMS y un anuncio por altavoz](../assets/images/concepts_flow.svg)

1. **Destinos** - las personas se convierten en las formas de contactarlas, usando sus datos de [Recipient](#recipient)
2. **Deliveries** - se eligen las [Deliveries](#delivery) que corresponden, por defecto o mediante [Scenarios](#scenario)
3. **Notificaciones** - cada delivery toma los destinos que puede usar y envía una notificación adecuada,
   de modo que un correo puede tener un diseño HTML completo con imágenes, mientras que el altavoz de la cocina recibe un breve mensaje hablado

## Destino (Target) { #target }
- Quién o qué recibe la notificación y cómo
  - Destinos *directos*
    - dirección de correo electrónico
    - número de teléfono
    - `entity_id` o `device_id`, por ejemplo para hacer un anuncio en un dispositivo Alexa
    - un ID personalizado para un transporte especializado como Telegram
  - Destinos *indirectos*, que pueden convertirse en destinos directos
    - `person_id` para usar las funciones de *Recipient*
    - los selectores de destino estándar de Home Assistant, `label_id`, `floor_id` y `area_id`
    - destinos de *grupo* (grupos de Home Assistant tanto nuevos como antiguos)
- Los destinos pueden asignarse a una **Categoría de destino** concreta, como `discord_channel:839439434`; consulta [Prefijos de categoría](../usage/targets.md#category-prefixes)
- Cada destino lo toma de la lista la integración más adecuada para gestionarlo
  - Por ejemplo, una entidad Notify de Alexa Devices la gestiona el transporte Alexa Devices, mientras que una entidad Notify genérica recurre al transporte Notify Entity, menos capaz
- Consulta [Targets](../usage/targets.md) para más información

## Destinatario (Recipient) { #recipient }
- Una persona, con dirección de correo, número de teléfono, dispositivos móviles o destinos personalizados opcionales
  - Por defecto se descubren automáticamente a partir de las cuentas de usuario y entidades de persona de Home Assistant
- Facilita referirse a personas en las automatizaciones: usa `person.joe_mctest` en lugar de recordar el correo de Joe en cada notificación. También funciona con números de teléfono si hay una integración SMS compatible, o con identificadores personalizados como Telegram o Discord
- Cada destinatario tiene además una entidad `switch` de Home Assistant, para evitar fácilmente que alguien reciba notificaciones
- Consulta [People](../configuration/people.md) y [Recipes](../recipes/index.md) para más detalles

## Transporte (Transport) { #transport }

- Un *transporte* es el medio técnico para notificar, normalmente usando una de las integraciones de Home Assistant ya instaladas
- Los *adaptadores de transporte* son lo que diferencia a Supernotify de los grupos Notify normales
  - Aunque un grupo Notify parece permitir notificaciones multicanal sencillas, en la práctica cada transporte tiene estructuras `data` distintas (¡y `data` dentro de `data`!), direccionamiento, etc., así que al final las notificaciones se reducen al mínimo común, como solo `message`
- Supernotify incluye adaptadores para transportes comunes como correo electrónico, push móvil, SMS y Alexa, además de un adaptador *Generic* que puede envolver cualquier otra acción de Home Assistant
- El adaptador de transporte permite enviar una sola notificación a muchas plataformas, aunque tengan interfaces distintas e incompatibles entre sí
- Adapta las notificaciones al transporte, eliminando atributos que no acepta, reorganizando las estructuras `data`, seleccionando solo los destinos apropiados y permitiendo ajustes adicionales cuando es posible
- Cada transporte tiene una configuración por defecto que permite ajustar muchos detalles y valores predeterminados, sin tener que repetirlos en cada notificación
- Consulta [Transports](../transports/index.md) para más detalles

## Entrega (Delivery) { #delivery }

- Una **Delivery** define cada canal de notificación que quieres usar
  - De serie, cada transporte tiene una delivery con el mismo nombre, por ejemplo `email` o `mobile_push`
  - Algunos transportes crean automáticamente deliveries adicionales, como `alexa_devices_announce_all` o `chime_siren_all`
  - Con YAML se pueden crear más deliveries, por ejemplo `html_email` además del `email` de texto plano, o deliveries distintas para asistentes de voz concretos
- Los transportes que pueden seleccionar destinos de forma inequívoca, como correo, push móvil, SMS, Alexa Devices y Notify Entity, se incluyen por defecto al gestionar destinos
  - Los demás pueden incluirse mediante configuración, usando Scenarios o pidiéndolo en una notificación
- Puedes definir tus propias deliveries, con el nombre que elijas, y tener varias para un mismo transporte, por ejemplo `plain_email` y `html_email`
- El [transporte Generic](../transports/generic.md) actúa como *caja de herramientas* para crear una delivery para casi cualquier cosa que Home Assistant pueda hacer y que no cubra ya un transporte estándar
- Consulta [Deliveries](../configuration/deliveries.md) y [Recipes](../recipes/index.md) para más detalles

## Escenario (Scenario) { #scenario }
- Un paquete de ajustes que puede activarse por nombre o automáticamente mediante condiciones de Home Assistant
- Los scenarios pueden seleccionarse manualmente con un valor `apply_scenarios` en el bloque `data` de la notificación, o automáticamente con un bloque `conditions` estándar de Home Assistant
  - Las condiciones incluyen el texto del mensaje, así que una notificación de Frigate sobre pájaros en el patio puede tratarse distinto que un intruso en una ventana
- Usa scenarios para que las notificaciones sean más discretas de noche, más festivas en vacaciones, o para dar prioridad a ciertos mensajes
- Permiten aplicar cambios en un solo lugar a muchas deliveries o notificaciones, y son la clave para simplificar radicalmente las llamadas de notificación en tus automatizaciones
- Consulta [Scenarios](../configuration/scenarios.md) y [Recipes](../recipes/index.md) para más detalles

## Prioridad (Priority) { #priority }
- Un nivel de urgencia para las notificaciones
   - No existe una forma estándar de priorizar notificaciones, ni dentro ni fuera de Home Assistant
   - Supernotify tiene su propio esquema de 5 niveles, que sigue las prácticas más comunes, de `minimum` a `critical`
   - La prioridad puede usarse en reglas de scenarios y deliveries, y transmitirse a las integraciones de notificación que la admitan
   - Supernotify tiene su propia integración de correo, que traduce la prioridad a un formato que entienden Outlook, Apple Mail, etc.

!!! info
    Para los más técnicos, hay un [Diagrama de clases](../developer/class_diagram.md) de las clases principales correspondientes a estos conceptos.

# Principios fundamentales { #core-principles }

1. Una notificación solo necesita un mensaje; todo lo demás puede tomar valores por defecto, incluidos todos los destinos
2. Lo que definas en una llamada de acción tiene prioridad sobre los valores por defecto
   - Esto puede ajustarse con opciones como `target_usage`
   - El registro de personas solo se usa para generar destinos si no se indica ninguno
3. Acción > Scenario > Delivery > Transport para configuración y valores por defecto
4. Lo menos exigente posible en cómo se configura y se llama
   - Los destinos pueden organizarse en subcategorías, o ser una gran lista de IDs de entidad, IDs de dispositivo, correos y números de teléfono
   - Las opciones de `data` de la acción, como `delivery`, pueden ser un valor único, una lista o un diccionario

## Desarrolladores { #developers }

Consulta [Developer Concepts](../developer/concepts.md) para ver cómo fluyen las notificaciones a través de deliveries, destinos y *Envelopes*, y los [Design Principles](../developer/principles.md).
