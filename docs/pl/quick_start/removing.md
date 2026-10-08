---
title: Usuwanie
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Usuń Supernotify dla Home Assistant i posprzątaj to, co po nim zostało
---

# Usuwanie Supernotify

W menu HACS wybierz `Supernotify`, a następnie `Usuń` z menu `...`.

### Porządkowanie konfiguracji { #cleaning-up-config }

1. Ręcznie utworzone pliki YAML w katalogu `config` pozostaną nietknięte; usuń je samodzielnie, jeśli masz pewność, że nie będą już potrzebne.
2. Zarchiwizowane powiadomienia pozostaną, domyślnie w katalogu `/config/archive/supernotify`, o ile nie skonfigurowano inaczej. W razie potrzeby usuń ten katalog.
3. Jeśli używasz kamer lub załączników graficznych, mogą pozostać pliki multimedialne, domyślnie w katalogu `/config/media/supernotify`, o ile nie skonfigurowano inaczej. W razie potrzeby usuń ten katalog.
4. Mogą pozostać szablony, domyślnie w katalogu `supernotify/templates` w katalogu konfiguracji Home Assistant, o ile nie skonfigurowano inaczej. W razie potrzeby usuń ten katalog.
