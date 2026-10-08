---
title: Entfernen
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Supernotify für Home Assistant entfernen und Überbleibsel aufräumen
---

# Supernotify entfernen

Wählen Sie im HACS-Menü `Supernotify` und im Menü `...` den Punkt `Entfernen`.

### Konfiguration aufräumen { #cleaning-up-config }

1. Von Hand angelegte YAML-Dateien im Verzeichnis `config` bleiben unberührt. Entfernen Sie sie selbst, wenn Sie sicher sind, dass sie nicht mehr gebraucht werden.
2. Archivierte Benachrichtigungen bleiben erhalten, standardmäßig im Verzeichnis `/config/archive/supernotify`, sofern nicht anders konfiguriert. Entfernen Sie dieses Verzeichnis bei Bedarf.
3. Bei Kameras oder Bildanhängen können Mediendateien zurückbleiben, standardmäßig im Verzeichnis `/config/media/supernotify`, sofern nicht anders konfiguriert. Entfernen Sie dieses Verzeichnis bei Bedarf.
4. Vorlagen können zurückbleiben, standardmäßig im Verzeichnis `supernotify/templates` unterhalb Ihres Home Assistant-Konfigurationsverzeichnisses, sofern nicht anders konfiguriert. Entfernen Sie dieses Verzeichnis bei Bedarf.
