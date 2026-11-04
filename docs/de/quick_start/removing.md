---
title: Entfernen
tags:
  - installation
  - marketplace
  - configuration
  - quickstart
description: Supernotify für Home Assistant entfernen und Überbleibsel aufräumen
---

# Supernotify entfernen

Gehen Sie zu **Einstellungen → Marketplace**, öffnen Sie **Supernotify** und wählen Sie im Drei-Punkte-Menü **Deinstallieren**. Solange es noch eingerichtet ist, lässt es sich nicht deinstallieren. Entfernen Sie es also zuerst unter **Einstellungen → Geräte & Dienste**, oder wählen Sie **Löschen und deinstallieren**, was auch seine Geräte und Entitäten löscht.

Vor Home Assistant 2026.11: Wählen Sie im HACS-Menü `Supernotify` und im Menü `...` den Punkt `Entfernen`.

### Konfiguration aufräumen { #cleaning-up-config }

1. Von Hand angelegte YAML-Dateien im Verzeichnis `config` bleiben unberührt. Entfernen Sie sie selbst, wenn Sie sicher sind, dass sie nicht mehr gebraucht werden.
2. Archivierte Benachrichtigungen bleiben erhalten, standardmäßig im Verzeichnis `/config/archive/supernotify`, sofern nicht anders konfiguriert. Entfernen Sie dieses Verzeichnis bei Bedarf.
3. Bei Kameras oder Bildanhängen können Mediendateien zurückbleiben, standardmäßig im Verzeichnis `/config/media/supernotify`, sofern nicht anders konfiguriert. Entfernen Sie dieses Verzeichnis bei Bedarf.
4. Vorlagen können zurückbleiben, standardmäßig im Verzeichnis `supernotify/templates` unterhalb Ihres Home Assistant-Konfigurationsverzeichnisses, sofern nicht anders konfiguriert. Entfernen Sie dieses Verzeichnis bei Bedarf.
