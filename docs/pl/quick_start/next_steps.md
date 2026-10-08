---
title: Co dalej
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: Co zrobić po pierwszym powiadomieniu Supernotify - powiadamiać z automatyzacji, dodać dashboard, wybrać, kto i co jest powiadamiane, oraz znaleźć pomysły w przepisach
---
# Co dalej

Zacznij od automatyzacji, bo do tego służą powiadomienia. Reszta jest opcjonalna i można ją robić w dowolnej kolejności.

## Dodaj powiadomienie do automatyzacji { #add-a-notification-to-an-automation }

`supernotify.notify` to akcja jak każda inna, więc dodaje się ją do automatyzacji w zwykły sposób. Ten przykład wysyła powiadomienie, gdy zadziała czujnik ruchu w korytarzu.

Utwórz automatyzację z czujnikiem ruchu jako wyzwalaczem, następnie wybierz **Dodaj akcję** i wyszukaj Supernotify:

![Wybór akcji](../../assets/images/add_action_automation.png){width=600}

Wpisz wiadomość i wszystko inne, czego chcesz z [pierwszego powiadomienia](first_notification.md), na przykład cel lub delivery:

![Konfiguracja akcji](../../assets/images/automation_action_simple.png){width=600}

```yaml title="Automatyzacja z czujnikiem ruchu"
alias: Hallway motion notification
triggers:
  - trigger: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
actions:
  - action: supernotify.notify
    data:
      title: Motion detected
      message: Something is moving in the hallway
      target: person.john_mcdoe
```

Aby usłyszeć je także na głośnikach, dodaj `alexa_devices_announce_all` i `mobile_push` jako delivery. [Wysyłanie powiadomień](../../usage/notifying.md) opisuje wszystko, co jeszcze potrafi ta akcja.

Pełniejszy przykład, z komunikatami głosowymi i obrazem z kamery, znajdziesz w przepisie [Ktoś jest przy drzwiach](../../recipes/someone_at_the_door.md).

## Dodaj dashboard { #add-a-dashboard }

[Supernotify Cards](https://github.com/lollox80/supernotify-cards) oferuje wiele wyspecjalizowanych kart do sterowania powiadomieniami i ich monitorowania, ręcznego wysyłania oraz testowania konfiguracji.

![Karty przeglądu i transportów](../../assets/images/cards.png)

Strona [Dashboard](../../configuration/dashboard.md) zawiera kompletny przykład do wklejenia w nowy dashboard, który potem można edytować wizualnie.

## Włączaj i wyłączaj osoby oraz delivery { #switch-people-and-deliveries-on-and-off }

Każda osoba znana Supernotify ma w Home Assistant encję `switch`, podobnie jak każde delivery. Wyłącz ją, aby komuś nie przeszkadzać albo na chwilę wyciszyć głośniki, bez zmieniania automatyzacji.

## Powiadamiaj tylko wybrane urządzenia { #notify-just-some-devices }

Celem może być **Obszar**, **Piętro** lub **Etykieta**, a także osoba lub urządzenie, więc powiadomienie może trafić na głośniki na parterze albo do wszystkiego, co ma etykietę kuchni. Zobacz [Targets](../../usage/targets.md) oraz [FAQ](../../faqs.md) z częstymi pytaniami.

## Dostosuj ustawienia { #tune-the-settings }

Archiwizację, wykrywanie duplikatów i porządkowanie można zmienić w opcji **Konfiguruj** integracji, w **Ustawienia → Urządzenia i usługi**. Zobacz [Archiwizację](../../configuration/archiving.md) i [Wykrywanie duplikatów](../../configuration/dupe_detection.md).

## Zainspiruj się { #be-inspired }

Wiele pomysłów z przykładową konfiguracją znajdziesz w [przepisach](../../recipes/index.md).

## Pójdź dalej z YAML { #go-further-with-yaml }

Odrobina konfiguracji YAML daje więcej możliwości, a wszystko to jest opcjonalne:

- Nadaj osobom adres e-mail lub numer telefonu, w [People](../../configuration/people.md)
- Utwórz własne delivery, na przykład e-mail HTML albo stały zestaw głośników, w [Deliveries](../../configuration/deliveries.md)
- Zmień zachowanie powiadomień w nocy albo gdy nikogo nie ma w domu, za pomocą [Scenarios](../../configuration/scenarios.md)
- Dołączaj zdjęcia z kamer, w [Multimedia](../../configuration/multimedia.md)

[Pojęcia zaawansowane](advanced_concepts.md) wyjaśniają stojące za tym idee, a [Konfiguracja](../../configuration/index.md) to dokumentacja referencyjna.

## Uzyskaj pomoc { #get-help }

Zapytaj na stronie [Discussions](https://github.com/rhizomatics/supernotify/discussions) albo skorzystaj z agenta AI - zobacz ostatnią odpowiedź w [FAQ](../../faqs.md).
