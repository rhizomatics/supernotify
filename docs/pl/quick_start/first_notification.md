---
title: Wyślij pierwsze powiadomienie
tags:
  - quickstart
  - developer tools
  - notification
description: Wyślij pierwsze powiadomienie Supernotify z Home Assistant - do wszystkich, do jednej osoby i na głośniki Alexa
---
# Wyślij pierwsze powiadomienie

Wszystko na tej stronie robi się w interfejsie Home Assistant, zaraz po [instalacji](installation.md). Każdy krok pokazuje też YAML, dla tych, którzy go wolą.

## 1. Powiadom wszystkich { #1-notify-everyone }

Otwórz [kartę Akcje](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab) w **Narzędziach deweloperskich**, wybierz akcję `supernotify.notify`, wpisz wiadomość i naciśnij **Wykonaj akcję**.

![Akcja w narzędziach deweloperskich](../../assets/images/tools_action_notify.png){width=600}

```yaml title="Wiadomość do wszystkich"
action: supernotify.notify
data:
  message: Something went off in the basement
```

Powiadomienie potrzebuje tylko wiadomości. Bez żadnych dodatkowych danych trafia na każdy telefon i tablet z aplikacją Home Assistant, do wszystkich domowników.

## 2. Powiadom jedną osobę { #2-notify-one-person }

To pewnie więcej osób, niż chcesz. Aby to ograniczyć, wybierz encje `person` albo pojedyncze urządzenia mobilne jako **cele** (targets):

![Powiadomienie wszystkich urządzeń mobilnych jednej osoby](../../assets/images/person_notify.png){width=400}

```yaml title="Wiadomość do jednej osoby"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

Teraz dostają je tylko urządzenia Johna. Wybranie osoby zamiast telefonu sprawia, że powiadomienie dotrze także wtedy, gdy John zmieni telefon.

## 3. Wybierz sposób wysyłki { #3-choose-how-its-sent }

Pole **Delivery** zawiera sposoby wysyłania powiadomień znalezione przez Supernotify. Jeśli je pominiesz, Supernotify wybierze za Ciebie; jeśli coś wybierzesz, użyte zostaną tylko te pozycje.

![Wybór delivery](../../assets/images/delivery_choice.png)

Jeśli masz urządzenia Alexa, użyj `alexa_devices_announce_all` lub `alexa_devices_speak_all`. (Announce dodaje na początku sygnał dźwiękowy, speak nie.) Można je połączyć z e-mailem i powiadomieniami w aplikacji mobilnej w jednym powiadomieniu.

```yaml title="Głośniki i telefony razem"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

Każdy sposób dostaje odpowiednie dla siebie powiadomienie, więc głośniki wypowiadają wiadomość, a telefony ją wyświetlają.

Gdy to działa, następnym krokiem jest [dodanie powiadomienia do automatyzacji](next_steps.md#add-a-notification-to-an-automation).
