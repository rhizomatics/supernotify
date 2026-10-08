---
title: Instalación
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Instala Supernotify para Home Assistant desde HACS y configúralo desde la interfaz, sin YAML
---

# Instalación

## Instalar desde HACS { #install-from-hacs }

Primero, asegúrate de tener **HACS** instalado.

Si no es así, consulta las [instrucciones de HACS](https://hacs.xyz/docs/use/). Supernotify es uno de los repositorios predeterminados de HACS, así que no hace falta configurar ningún repositorio personalizado.

En la página de HACS de Home Assistant, selecciona **Supernotify** en la lista de integraciones disponibles, descárgalo y reinicia Home Assistant.

![Selección en HACS](../../assets/images/hacs_select.png){width=400}

## Añadir la integración { #add-the-integration }

Ve a **Ajustes → Dispositivos y servicios → Añadir integración** y busca **Supernotify**. Acepta los valores predeterminados.

![Añadir la integración](../../assets/images/new_integration.png)

## Detección y valores predeterminados { #discovery-and-defaults }

Con lo anterior ya tienes todo lo necesario para que funcionen las primeras notificaciones.

Supernotify mira lo que ya hay en Home Assistant y encuentra:

- **Personas** - todos los que tienen una *Persona* o un *Usuario* en Home Assistant, y los teléfonos o tabletas en los que usan la aplicación de Home Assistant
- **Formas de notificar** - notificaciones push al móvil, una integración de correo SMTP existente, cualquier entidad notify y dispositivos como altavoces Alexa o timbres, si los tienes

Crea una *delivery* para cada forma de notificar que encuentra, además de algunas de conveniencia, como `chime_siren_all` y `alexa_devices_announce_all`, si tienes esos dispositivos.

El archivo, la detección de duplicados y los ajustes de mantenimiento se pueden cambiar después desde la opción **Configurar** de la integración.

Ahora [envía tu primera notificación](first_notification.md).
