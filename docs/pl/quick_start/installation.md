---
title: Instalacja
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Zainstaluj Supernotify dla Home Assistant z HACS i skonfiguruj go w interfejsie, bez YAML
---

# Instalacja

## Instalacja z HACS { #install-from-hacs }

Najpierw upewnij się, że masz zainstalowany **HACS**.

Jeśli nie, zajrzyj do [instrukcji HACS](https://hacs.xyz/docs/use/). Supernotify należy do domyślnych repozytoriów HACS, więc nie trzeba konfigurować własnego repozytorium.

Na stronie HACS w Home Assistant wybierz **Supernotify** z listy dostępnych integracji, pobierz go i uruchom ponownie Home Assistant.

![Wybór w HACS](../../assets/images/hacs_select.png){width=400}

## Dodanie integracji { #add-the-integration }

Przejdź do **Ustawienia → Urządzenia i usługi → Dodaj integrację** i wyszukaj **Supernotify**. Zaakceptuj wartości domyślne.

![Dodawanie integracji](../../assets/images/new_integration.png)

## Wykrywanie i wartości domyślne { #discovery-and-defaults }

To wszystko, czego potrzeba, aby pierwsze powiadomienia zaczęły działać.

Supernotify sprawdza, co już jest w Home Assistant, i znajduje:

- **Osoby** - każdego, kto ma *Osobę* lub *Użytkownika* w Home Assistant, wraz z telefonami i tabletami, na których korzysta z aplikacji Home Assistant
- **Sposoby powiadamiania** - powiadomienia push na telefon, istniejącą integrację e-mail SMTP, wszystkie encje notify oraz urządzenia takie jak głośniki Alexa czy dzwonki, jeśli je masz

Dla każdego znalezionego sposobu powiadamiania tworzy *delivery*, a do tego kilka pomocniczych, takich jak `chime_siren_all` i `alexa_devices_announce_all`, jeśli masz takie urządzenia.

Archiwum, wykrywanie duplikatów i ustawienia porządkowania można później zmienić w opcji **Konfiguruj** integracji.

Teraz [wyślij pierwsze powiadomienie](first_notification.md).
