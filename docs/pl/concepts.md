---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Podstawowe koncepcje Supernotify dla Home Assistant, w tym Transport, Delivery, Scenario i Recipient
---
# Podstawowe koncepcje

## Jak to wszystko działa razem { #how-it-fits-together }

Jedno powiadomienie z automatyzacji może zamienić się w kilka różnych powiadomień, każde dopasowane
do sposobu, w jaki jest wysyłane.

![Jedno powiadomienie z automatyzacji staje się e-mailem, dwoma powiadomieniami push, SMS-em i komunikatem z głośnika](../assets/images/concepts_flow.svg)

1. **Cele** - osoby są zamieniane na sposoby, w jakie można się z nimi skontaktować, na podstawie ich danych [Recipient](#recipient)
2. **Deliveries** - wybierane są odpowiednie [Deliveries](#delivery), domyślnie lub przez [Scenarios](#scenario)
3. **Powiadomienia** - każda delivery bierze cele, których może użyć, i wysyła dopasowane powiadomienie,
   dzięki czemu e-mail może mieć pełny układ HTML ze zdjęciami, a głośnik w kuchni dostaje krótki komunikat głosowy

## Cel (Target) { #target }
- Kto lub co otrzymuje powiadomienie i w jaki sposób
  - Cele *bezpośrednie*
    - adres e-mail
    - numer telefonu
    - `entity_id` lub `device_id`, na przykład do komunikatu przez urządzenie Alexa
    - własny identyfikator dla specjalistycznego transportu, np. Telegram
  - Cele *pośrednie*, które można zamienić na cele bezpośrednie
    - `person_id`, aby korzystać z funkcji *Recipient*
    - standardowe selektory celów Home Assistant: `label_id`, `floor_id` i `area_id`
    - cele *grupowe* (zarówno nowe, jak i stare grupy Home Assistant)
- Cele można przypisać do konkretnej **Kategorii celu**, np. `discord_channel:839439434`; zobacz [Prefiksy kategorii](../usage/targets.md#category-prefixes)
- Każdy cel jest brany z listy przez integrację, która najlepiej go obsłuży
  - Na przykład encja Notify urządzenia Alexa jest obsługiwana przez transport Alexa Devices, a ogólna encja Notify trafia do mniej rozbudowanego transportu Notify Entity
- Zobacz [Targets](../usage/targets.md), aby dowiedzieć się więcej

## Odbiorca (Recipient) { #recipient }
- Osoba, z opcjonalnym adresem e-mail, numerem telefonu, urządzeniami mobilnymi lub własnymi celami
  - Domyślnie wykrywani automatycznie na podstawie kont użytkowników i encji osób już istniejących w Home Assistant
- Ułatwia to odwoływanie się do osób w automatyzacjach: użyj `person.joe_mctest`, zamiast pamiętać adres e-mail Joego w każdym powiadomieniu. Działa też z numerami telefonów, jeśli zainstalowana jest zgodna integracja SMS, lub z własnymi identyfikatorami, np. Telegram lub Discord
- Każdy odbiorca ma też encję `switch` w Home Assistant, dzięki czemu łatwo oszczędzić komuś powiadomień
- Zobacz [People](../configuration/people.md) i [Recipes](../recipes/index.md), aby poznać szczegóły

## Transport { #transport }

- *Transport* to techniczny sposób faktycznego powiadamiania, zwykle przez jedną z już zainstalowanych integracji Home Assistant
- *Adaptery transportu* stanowią o różnicy między zwykłymi grupami Notify a Supernotify
  - Grupa Notify pozornie pozwala łatwo wysyłać powiadomienia wieloma kanałami, ale w praktyce każdy transport ma inne struktury `data` (i `data` wewnątrz `data`!), adresowanie itd., więc powiadomienia trzeba w końcu sprowadzić do najmniejszego wspólnego zestawu atrybutów, np. samego `message`!
- Supernotify ma wbudowane adaptery dla popularnych transportów, takich jak e-mail, push mobilny, SMS i Alexa, oraz adapter *Generic*, który może opakować dowolną inną akcję Home Assistant
- Adapter transportu pozwala wysłać jedno powiadomienie na wiele platform, nawet jeśli mają różne i wzajemnie niezgodne interfejsy
- Dostosowuje powiadomienia do transportu: usuwa nieobsługiwane atrybuty, przekształca struktury `data`, wybiera tylko odpowiednie cele i, gdzie to możliwe, pozwala na dodatkowe dostrajanie
- Każdy transport ma konfigurację domyślną, która pozwala na wiele ustawień i wartości domyślnych, więc nie trzeba ich powtarzać w każdym powiadomieniu
- Zobacz [Transports](../transports/index.md), aby poznać szczegóły

## Dostarczanie (Delivery) { #delivery }

- **Delivery** definiuje każdy kanał powiadomień, którego chcesz używać
  - Domyślnie każdy transport ma delivery o tej samej nazwie, np. `email` lub `mobile_push`
  - Niektóre transporty automatycznie tworzą dodatkowe deliveries, np. `alexa_devices_announce_all` lub `chime_siren_all`
  - W YAML można tworzyć kolejne deliveries, np. `html_email` obok zwykłego tekstowego `email`, albo osobne deliveries dla konkretnych asystentów głosowych
- Transporty, które potrafią jednoznacznie wybrać cele, takie jak e-mail, push mobilny, SMS, Alexa Devices i Notify Entity, są domyślnie uwzględniane przy obsłudze celów
  - Inne można uwzględnić przez konfigurację, za pomocą Scenarios lub prosząc o nie w powiadomieniu
- Możesz definiować własne deliveries o wybranej nazwie i mieć kilka deliveries dla jednego transportu, np. `plain_email` i `html_email`
- [Transport Generic](../transports/generic.md) działa jak *skrzynka z narzędziami* do tworzenia delivery dla niemal wszystkiego, co potrafi Home Assistant, a czego nie obejmuje jeszcze standardowy transport
- Zobacz [Deliveries](../configuration/deliveries.md) i [Recipes](../recipes/index.md), aby poznać szczegóły

## Scenariusz (Scenario) { #scenario }
- Pakiet ustawień, który można włączyć po nazwie lub automatycznie za pomocą warunków Home Assistant
- Scenarios można wybrać ręcznie wartością `apply_scenarios` w bloku `data` powiadomienia albo automatycznie standardowym blokiem `conditions` Home Assistant
  - Warunki uwzględniają treść wiadomości, więc powiadomienie Frigate o ptakach na tarasie można obsłużyć inaczej niż intruza przy oknie
- Używaj scenarios, aby powiadomienia były mniej uciążliwe w nocy, bardziej świąteczne w święta lub aby nadać priorytet niektórym wiadomościom
- Pozwalają wprowadzać zmiany w jednym miejscu dla wielu deliveries lub powiadomień i są kluczem do radykalnego uproszczenia wywołań powiadomień w automatyzacjach
- Zobacz [Scenarios](../configuration/scenarios.md) i [Recipes](../recipes/index.md), aby poznać szczegóły

## Priorytet (Priority) { #priority }
- Poziom pilności powiadomień
   - Nie ma standardowego sposobu priorytetyzacji powiadomień, ani w Home Assistant, ani poza nim
   - Supernotify ma własny 5-poziomowy schemat zgodny z najczęstszymi praktykami, od `minimum` do `critical`
   - Priorytetu można używać w regułach scenarios i deliveries oraz przekazywać go do integracji powiadomień, które go obsługują
   - Supernotify ma własną integrację e-mail, która przekłada priorytet na format zrozumiały dla Outlooka, Apple Mail itp.

!!! info
    Dla zainteresowanych technicznie jest [Diagram klas](../developer/class_diagram.md) klas podstawowych odpowiadających tym koncepcjom.

# Podstawowe zasady { #core-principles }

1. Powiadomienie potrzebuje tylko wiadomości; wszystko inne może mieć wartości domyślne, łącznie ze wszystkimi celami
2. To, co zdefiniujesz w wywołaniu akcji, ma pierwszeństwo przed wartościami domyślnymi
   - Można to dostroić opcjami takimi jak `target_usage`
   - Rejestr osób służy do tworzenia celów tylko wtedy, gdy nie podano żadnych celów
3. Akcja > Scenario > Delivery > Transport dla konfiguracji i wartości domyślnych
4. Jak najmniej wymagań co do sposobu konfiguracji i wywołania
   - Cele mogą być pogrupowane w podkategorie albo stanowić jedną dużą listę identyfikatorów encji, urządzeń, adresów e-mail i numerów telefonów
   - Opcje `data` akcji, takie jak `delivery`, mogą być pojedynczą wartością, listą lub słownikiem

## Deweloperzy { #developers }

Zobacz [Developer Concepts](../developer/concepts.md), aby dowiedzieć się, jak powiadomienia przechodzą przez deliveries, cele i *Envelopes*, oraz [Design Principles](../developer/principles.md).
