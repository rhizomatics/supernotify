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
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Dodaj do HACS">
   </a>
<br/>
<br/>
<br/>

**Ujednolicone Powiadomienia dla Home Assistant**

**Ujednolicony interfejs powiadomień** zbudowany na wbudowanej platformie `notify` Home Assistant, który znacznie upraszcza obsługę wielu kanałów powiadomień i złożonych scenariuszy — w tym powiadomień wielokanałowych, warunkowych, akcji mobilnych, zdjęć z kamer, dzwonków i szablonowych e-maili HTML.

Supernotify ma jeden cel — **sprawić, by najprostsze możliwe powiadomienie wysyłało tyle powiadomień ile potrzeba, bez kodu i z minimalną konfiguracją**.

Dzięki temu automatyzacje, skrypty i aplikacje AppDaemon pozostają proste i łatwe w utrzymaniu, a wszystkie szczegóły i reguły są zarządzane w jednym miejscu. Najmniejsze możliwe powiadomienie — zawierające tylko wiadomość — może wystarczyć do uruchomienia wszystkiego. Zmień adresy e-mail w jednym miejscu, a Supernotify zadba o resztę.

Zaledwie dwie linie prostego YAML wystarczą, by rozpocząć wysyłanie powiadomień push do wszystkich zarejestrowanych w domu, bez konfigurowania nazw aplikacji mobilnych.


## Dystrybucja

Supernotify to komponent niestandardowy dostępny przez [Home Assistant Community Shop](https://hacs.xyz) (**HACS**). Jest darmowy i open source na licencji [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0).

## Dokumentacja

Zapoznaj się z [Wprowadzeniem](https://supernotify.rhizomatics.org.uk/getting_started/), wyjaśnieniem [podstawowych koncepcji](https://supernotify.rhizomatics.org.uk/concepts/) i dostępnymi [adapterami transportu](https://supernotify.rhizomatics.org.uk/transports/). [Powiadamianie](https://supernotify.rhizomatics.org.uk/usage/notifying/) pokazuje, jak wywoływać Supernotify z automatyzacji lub strony narzędzi dla deweloperów.

Dostępnych jest wiele [przepisów](https://supernotify.rhizomatics.org.uk/recipes/) z przykładowymi konfiguracjami lub przeglądaj według [tagów](https://supernotify.rhizomatics.org.uk/tags/).


## Funkcje

* Jedna akcja -> Wiele powiadomień
    * Usuń powtarzającą się konfigurację i kod z automatyzacji
    * Adaptery automatycznie dostosowują dane powiadomień do każdej integracji
    * Na przykład użyj z [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints) do otrzymywania zdjęć z kamer e-mailem
* Automatyczna konfiguracja
    * Konfiguracja dostarczania dla powiadomień push na telefon, e-mail (SMTP) i encji powiadomień ustawiana automatycznie
    * Aplikacje mobilne wykrywane automatycznie, w tym producent i model telefonu
    * Urządzenia Alexa do dzwonków wykrywane automatycznie
* Poza integracjami `notify`
    * Dzwonki, syreny, SMS, TTS, ogłoszenia i dźwięki Alexa, wywołania API, urządzenia MQTT, Gotify, ntfy
    * Wszystkie standardowe implementacje `notify` i `notify.group` dostępne
    * Znacznie uproszczone korzystanie z powiadomień push na telefon, np. dla iPhone
* Powiadomienia warunkowe
    * Używanie standardowych `conditions` Home Assistant
    * Dodatkowe zmienne warunków, w tym wiadomość i priorytet
    * Połącz z wykrywaniem obecności dla kontekstowych powiadomień
* **Scenariusze** dla prostej i zwięzłej konfiguracji
    * Pakuj wspólne bloki konfiguracji i logiki warunkowej
    * Stosuj na żądanie (`red_alert`, `nerdy`) lub automatycznie na podstawie warunków
* Ujednolicony model osoby
    * Zdefiniuj e-mail, numer SMS lub urządzenie mobilne, a następnie używaj encji `person` w akcjach powiadomień
    * Osoby są automatycznie konfigurowane wraz z aplikacjami mobilnymi
* Łatwe **szablony e-mail HTML**
    * Standardowy Jinja2 Home Assistant, zdefiniowany w konfiguracji YAML, wywołaniach akcji lub jako samodzielne pliki
    * Domyślny szablon ogólny w zestawie
* **Akcje mobilne**
    * Ustaw jeden spójny zestaw akcji mobilnych dla wielu powiadomień
    * Uwzględnij akcje *drzemki* do wyciszania na podstawie kryteriów
* Elastyczne **zrzuty obrazów**
    * Obsługuje kamery, obrazy MQTT i adresy URL obrazów
    * Przesuwaj kamery do predefiniowanych pozycji PTZ przed i po wykonaniu zrzutu
* Wybór poziomu konfiguracji
    * Ustaw wartości domyślne na poziomie adaptera transportu, dostarczania i akcji
* Tłumienie **zduplikowanych powiadomień**
    * Ustaw czas oczekiwania przed ponownym zezwoleniem
* **Archiwizacja** powiadomień i **wsparcie debugowania**
    * Opcjonalne archiwizowanie powiadomień do systemu plików i/lub tematu MQTT
    * Zawiera pełne informacje debugowania
    * Dostarczenia, transporty, odbiorcy i scenariusze eksponowane jako encje w interfejsie Home Assistant


## Trochę YAML wymagane

Supernotify obsługuje obecnie tylko [konfigurację opartą na YAML](https://supernotify.rhizomatics.org.uk/configuration/yaml/). Zaledwie 2 linie konfiguracji kopiuj-wklej wystarczają do wielu zastosowań:

```yaml title="Z domyślnymi 2 liniami YAML"
  - action: notify.supernotify
    data:
        message: Cześć! Test Supernotify wysyłający do aplikacji mobilnych wszystkich
```


##  Rhizomatics Open Source dla Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Automatyczne uzbrajanie i rozbrajanie paneli alarmowych Home Assistant za pomocą fizycznych przycisków, obecności, kalendarzy i innych
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - Przechwytywanie zdarzeń OpenTelemetry (OTLP) i Syslog dla Home Assistant


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integracja z kamerami ANPR/ALPR tablic rejestracyjnych przez system plików do MQTT
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Automatyczne powiadomienia przez MQTT o aktualizacjach obrazów Docker

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
