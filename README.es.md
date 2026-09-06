![Supernotify](../assets/images/dark_icon.png){ align=left }

# Supernotify

[![Rhizomatics Open Source](https://img.shields.io/badge/rhizomatics%20open%20source-lightseagreen)](https://github.com/rhizomatics) [![hacs][hacsbadge]][hacs]

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
![Coverage](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/coverage.svg)
![Tests](https://raw.githubusercontent.com/rhizomatics/supernotify/refs/heads/badges/badges/tests.svg)
[![Github Deploy](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rhizomatics/supernotify/actions/workflows/deploy.yml)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)

 <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=rhizomatics&repository=supernotify" target="_blank" rel="noopener noreferrer">
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Agregar a HACS">
   </a>
<br/>
<br/>
<br/>

**Notificaciones Unificadas para Home Assistant**

### CAMBIO IMPORTANTE v2.0.0

>> La versión `2.0.0` de SuperNotify pasa a una configuración nativa de UI de Home Assistant ('ConfigFlow'). Si ya tienes una configuración simple existente, todo se migrará automáticamente por ti y no se necesitará YAML.

>> Si tienes una configuración avanzada (entregas, escenarios, cámaras, personas, acciones, etc.), se generará una *reparación* para moverlas a un nuevo archivo `supernotify.yaml` y añadir una instrucción `include` a tu `configuration.yaml`. O puedes optar por mover la configuración fuera del bloque `notify` manualmente, como prefieras.

>> En cualquier caso, no se eliminará ni se comentará nada, por lo que será fácil revertir el cambio. Elimina la configuración antigua cuando estés seguro de que la nueva versión funciona correctamente para ti.

Una **interfaz de notificación unificada** sobre la plataforma `notify` integrada de Home Assistant, para simplificar en gran medida los canales de notificación múltiples y los escenarios complejos, incluyendo notificaciones multicanal, notificaciones condicionales, acciones móviles, capturas de cámara, carillones y correos electrónicos HTML basados en plantillas.

Supernotify tiene un único objetivo: **hacer que la notificación más simple posible envíe tantas notificaciones como sea necesario, sin código y con configuración mínima**.

Esto mantiene las automatizaciones, scripts y aplicaciones AppDaemon simples y fáciles de mantener, con todos los detalles y reglas gestionados en un solo lugar. La notificación más pequeña posible — solo un mensaje — puede ser suficiente para desencadenar todo lo necesario. Cambia las direcciones de correo electrónico en un solo lugar y deja que Supernotify determine qué aplicaciones móviles usar.

Con solo la configuración de la interfaz, comienza las notificaciones push móviles a todos los registrados en casa, sin configurar los nombres de las aplicaciones móviles en las notificaciones.


## Distribución

Supernotify es un componente personalizado disponible a través del [Home Assistant Community Shop](https://hacs.xyz) (**HACS**). Es gratuito y de código abierto bajo la [licencia Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0).

## Documentación

Prueba el [inicio rápido](https://supernotify.rhizomatics.org.uk/getting_started/), la explicación de los [conceptos fundamentales](https://supernotify.rhizomatics.org.uk/concepts/) y los [adaptadores de transporte](https://supernotify.rhizomatics.org.uk/transports/) disponibles. [Notificando](https://supernotify.rhizomatics.org.uk/usage/notifying/) muestra cómo llamar a Supernotify desde automatizaciones o la página de herramientas para desarrolladores.

Hay muchas [recetas](https://supernotify.rhizomatics.org.uk/recipes/) con fragmentos de configuración de ejemplo, o navega por [etiquetas](https://supernotify.rhizomatics.org.uk/tags/).


## Características

* Una acción -> Múltiples notificaciones
    * Elimina la configuración y el código repetitivos de las automatizaciones
    * Los adaptadores ajustan automáticamente los datos de notificación para cada integración
    * Por ejemplo, úsalo con un [Blueprint de Frigate](https://github.com/SgtBatten/HA_blueprints) para recibir capturas de cámara por correo electrónico
* Configuración automática
    * Configuración de entrega para notificaciones push móviles, correo electrónico (SMTP) y entidades de notificación configurada automáticamente
    * Aplicaciones móviles descubiertas automáticamente, incluyendo fabricante y modelo del teléfono
    * Dispositivos Alexa para carillones descubiertos automáticamente
* Más allá de las integraciones `notify`
    * Carillones, sirenas, SMS, TTS, anuncios y sonidos de Alexa, llamadas API, dispositivos MQTT, Gotify, ntfy
    * Todas las implementaciones estándar `notify` y `notify.group` disponibles
    * Uso muy simplificado de notificaciones push móviles, por ejemplo para iPhone
* Notificaciones condicionales
    * Usando `conditions` estándar de Home Assistant
    * Variables de condición adicionales, incluyendo mensaje y prioridad
    * Combina con la detección de ocupación para personalizar notificaciones
* **Escenarios** para configuración simple y concisa
    * Empaqueta bloques comunes de configuración y lógica condicional
    * Aplica bajo demanda (`red_alert`, `nerdy`) o automáticamente según condiciones
* Modelo unificado de personas
    * Define un correo electrónico, número SMS o dispositivo móvil y luego usa la entidad `person` en acciones de notificación
    * Las personas se configuran automáticamente junto con sus aplicaciones móviles
* **Plantillas de correo electrónico HTML** fáciles
    * Jinja2 estándar de Home Assistant, definido en configuración YAML, llamadas de acción o archivos independientes
    * Plantilla general predeterminada incluida
* **Acciones móviles**
    * Configura un conjunto consistente de acciones móviles para múltiples notificaciones
    * Incluye acciones de *posposición* para silenciar según criterios
* **Capturas de imágenes** flexibles
    * Compatible con cámaras, imágenes MQTT y URLs de imágenes
    * Reposiciona cámaras a preajustes PTZ antes y después de una captura
* Elección del nivel de configuración
    * Establece valores predeterminados a nivel de adaptador de transporte, entrega y acción
* Supresión de **notificaciones duplicadas**
    * Configura el tiempo de espera antes de volver a permitir
* **Archivo** de notificaciones y **soporte de depuración**
    * Archiva opcionalmente notificaciones en el sistema de archivos y/o tema MQTT
    * Incluye información completa de depuración
    * Entregas, transportes, destinatarios y escenarios expuestos como entidades en la interfaz de Home Assistant


## YAML solo para uso avanzado

Actualmente, Supernotify admite la configuración estándar mediante la interfaz de Home Assistant para la configuración básica, y [configuración YAML](https://supernotify.rhizomatics.org.uk/configuration/yaml/) para funciones avanzadas. YAML se mantendrá para facilitar el trabajo con bases de reglas más grandes.

Se puede hacer mucho con la sencilla configuración sin YAML, incluida la automatización de la configuración de push móvil. Consulta las [recetas](recipes/index.md) en la documentación, y este ejemplo de push móvil:

```yaml title="Con cero YAML, todo configurado por la interfaz"
  - action: supernotify.notify
    data:
        message: ¡Hola! Probando Supernotify enviando a las aplicaciones móviles de todos
```


##  Rhizomatics Open Source para Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Armar y desarmar automáticamente paneles de control de alarma de Home Assistant usando botones físicos, presencia, calendarios y más
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - Captura de eventos OpenTelemetry (OTLP) y Syslog para Home Assistant


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integración con cámaras ANPR/ALPR de matrículas a través del sistema de archivos a MQTT
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Notificación automática vía MQTT en actualizaciones de imágenes Docker

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
