---
title: Podstawowe pojęcia
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: Kilka pojęć Supernotify potrzebnych na start - cele, recipients, deliveries i priorytet oraz to, jak się ze sobą łączą
---
# Podstawowe pojęcia

## Jak to wszystko się łączy { #how-it-fits-together }

Jedno powiadomienie z automatyzacji może zamienić się w kilka różnych powiadomień, każde dopasowane do sposobu, w jaki jest wysyłane.

![Jedno powiadomienie z automatyzacji staje się e-mailem, dwoma powiadomieniami push, SMS-em i komunikatem z głośnika](../../assets/images/concepts_flow.svg)

Czytając obrazek od lewej do prawej:

1. **Kogo powiadomić** - [cele](#target). Osoby są zamieniane na sposoby, w jakie można do nich dotrzeć, na podstawie ich danych [recipient](#recipient)
2. **Delivery** - wybierane są odpowiednie [deliveries](#delivery), domyślnie albo dlatego, że o nie poproszono
3. **Powiadomienia** - każde delivery wybiera cele, których może użyć, i wysyła dopasowane do siebie powiadomienie, więc e-mail może mieć pełny układ HTML ze zdjęciami, a głośnik w kuchni dostaje krótki komunikat głosowy

Trzy słowa wystarczają do prawie wszystkiego, gdy korzystasz tylko z interfejsu.

## Cel (target) { #target }

Cel to **kto lub co jest powiadamiane**: osoba, telefon, głośnik, adres e-mail albo obszar, piętro lub etykieta oznaczające kilka urządzeń.

Jeśli pominiesz cele, powiadomienie trafi do wszystkich.

## Recipient { #recipient }

Recipient to **osoba, tak jak zna ją Supernotify**: jej telefony i tablety oraz opcjonalnie adres e-mail i numer telefonu. Recipients są znajdowani automatycznie na podstawie encji *Person* w Home Assistant.

Recipient nie jest innym rodzajem celu. Osoba to jedna z rzeczy, którymi może być cel, a recipient to miejsce, w którym Supernotify sprawdza, jak do niej dotrzeć. Dlatego `person.joe_mctest` działa jako cel i nie trzeba wpisywać adresu e-mail Joego w każdej automatyzacji.

## Delivery { #delivery }

Delivery to **jeden sposób wysłania powiadomienia**, mający nazwę, na przykład `mobile_push`, `email` albo `alexa_devices_announce_all`. Supernotify tworzy deliveries dla wszystkiego, co znajdzie w Twoim Home Assistant, i to one pojawiają się w polu **Delivery** akcji `supernotify.notify`.

Jeśli pominiesz deliveries, Supernotify użyje tych, które same potrafią ustalić, dokąd wysyłać, takich jak powiadomienia push i e-mail.

## Priorytet { #priority }

Priorytet określa, **jak pilne jest powiadomienie**, w pięciu poziomach: `minimum`, `low`, `medium`, `high` i `critical`. Jest opcjonalny i domyślnie wynosi `medium`. Priorytet jest przekazywany do telefonów, programów pocztowych i wszystkiego, co go rozumie.

## Jeszcze dwa, na później { #two-more-for-later }

Pojawiają się w całej dokumentacji, ale żadne z nich nie jest potrzebne na start.

- **Transport** to techniczny środek stojący za delivery, zwykle integracja Home Assistant, taka jak aplikacja mobilna, SMTP albo Alexa Devices. Delivery to transport wraz z ustawieniami, z którymi ma być używany, więc jeden transport może mieć kilka deliveries, na przykład zwykły `email` i `html_email`.
- **Scenario** to nazwany pakiet ustawień, który zmienia, które deliveries są używane i jak się zachowują, na przykład ciszej w nocy. Scenarios konfiguruje się w YAML.

[Pojęcia zaawansowane](advanced_concepts.md) omawiają oba, a także resztę możliwości konfiguracji YAML.
