---
title: Desinstalación
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Desinstala Supernotify para Home Assistant y limpia lo que quede
---

# Desinstalar Supernotify

En el menú de HACS, selecciona `Supernotify` y elige `Eliminar` en el menú `...`.

### Limpiar la configuración { #cleaning-up-config }

1. Los archivos YAML creados a mano en el directorio `config` no se tocan; elimínalos tú si tienes claro que no volverán a hacer falta.
2. Las notificaciones archivadas se conservan, por defecto en el directorio `/config/archive/supernotify`, salvo que se haya configurado otro. Elimina ese directorio si hace falta.
3. Si usas cámaras o imágenes adjuntas, pueden quedar archivos multimedia, por defecto en el directorio `/config/media/supernotify`, salvo que se haya configurado otro. Elimina ese directorio si hace falta.
4. Pueden quedar plantillas, por defecto en un directorio `supernotify/templates` dentro del directorio de configuración de Home Assistant, salvo que se haya configurado otro. Elimina ese directorio si hace falta.
