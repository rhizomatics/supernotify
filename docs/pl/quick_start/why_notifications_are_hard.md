---
title: Dlaczego powiadomienia są trudne
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Dlaczego w Home Assistant trudno jest wysłać jedno powiadomienie jednocześnie e-mailem, przez Telegram, push na telefon i SMS, wraz z katalogiem różnych stylów akcji powiadomień i tego, jak używa ich każda integracja
---
# Dlaczego powiadomienia w Home Assistant są trudne

Ta strona wyjaśnia, dlaczego wysłanie jednej wiadomości na kilka kanałów jest w Home Assistant trudniejsze, niż się
wydaje. To powód, dla którego istnieje Supernotify, a strona jest też pomyślana jako wkład w obecne prace
Home Assistant nad uproszczeniem powiadomień. Opisuje Home Assistant **2026.11**, sprawdzony w kodzie źródłowym.
Każde wydanie przenosi kolejne integracje na encje notify, więc niektóre wiersze
[tabeli](#integrations-and-their-styles) się zmienią.

## „Dlaczego nie mogę po prostu użyć grupy?" { #why-cant-i-just-use-a-group }

Załóżmy, że alert ma trafić na Twój telefon, na Twój e-mail, do rodzinnego czatu na Telegramie i SMS-em do kogoś bez
smartfona. Home Assistant ma grupy powiadomień, więc naturalne wydaje się utworzenie grupy z tych czterech i wysłanie
do niej. Są dwa rodzaje grup powiadomień i żaden nie pomieści wszystkich czterech.

**Pomocnik Grupa powiadomień**, tworzony w interfejsie, grupuje **encje notify** i wysyła przez
`notify.send_message`. Companion App, SMTP i bot Telegram mają encje notify, więc trzy z czterech się zmieszczą. SMS
nie: integracje SMS, takie jak Twilio SMS i ClickSend, mają tylko starszy styl akcji notify. Grupa wysyła tylko
`message` i `title`, a tytuł pomija dla wszystkich, jeśli którykolwiek członek nie obsługuje tytułów. Nie da się
dodać zdjęcia z kamery, przycisku w powiadomieniu na telefonie, treści e-maila w HTML ani niczego innego.

**Stara grupa notify**, tylko w YAML, grupuje starsze **akcje notify**, takie jak `notify.mobile_app_annas_phone` czy
`notify.smtp`. Telegram się do niej nie zmieści, bo jego akcja notify została usunięta w 2026.11 i została tylko
encja notify. Pozostałe trzy się zmieszczą, ale każdy członek dostaje to samo wywołanie:

- `target` znaczy dla każdego coś innego: adresy e-mail dla SMTP i numery telefonów dla Twilio, a własna akcja
  telefonu go ignoruje. Jeden `target` nie może pasować do wszystkich.
- `data` trafia do każdego członka bez względu na klucze. Obraz to `data.image` dla Companion App, `data.images`
  (lista plików lokalnych) dla SMTP i `data.media_url` dla Twilio SMS. Każdy członek dostaje oprócz swoich także
  klucze przeznaczone dla innych.
- Każdy członek może mieć stałe `data` w YAML, ale nie dane zmieniające się z każdym powiadomieniem, jak obraz dla
  tego konkretnego alertu.

Żaden z rodzajów grup nie wie, kogo powiadamia. Gdy telefon zostanie wymieniony, trzeba edytować grupę. Jeśli ktoś
jest poza domem albo wiadomość ma trafić tylko do osób w domu, grupa nie może o tym zdecydować. Grupy to tylko stałe
listy miejsc docelowych.

## Dlaczego tak jest { #why-its-like-this }

To niczyja wina. Przez dziesięć lat Home Assistant zyskał setki integracji powiadomień, każdą z potrzebami własnej
usługi, a wspólna część powiadomień zawsze była bardzo mała:

- **Wspólne jest tylko `message`.** `title` ma większość akcji. `target` istnieje w jednym stylu, a w innych nie, i w
  każdej integracji znaczy coś innego. Wszystko inne (obrazy, przyciski, priorytet, dźwięk, HTML, załączniki, akcje
  po dotknięciu) trafia w starym stylu pod dowolny klucz `data`, a w nowszym stylu do pól własnej akcji integracji.
  Żaden wspólny schemat ich nie obejmuje.
- **Ta sama idea ma różne nazwy.** Akcja po dotknięciu to `data.url` na iOS, ale `data.clickAction` na Androidzie,
  obie w Companion App. W ntfy to `click`, a w Prowl i Pushover `url`. Priorytet ma zakres od `-2` do `2` w Pushover
  i Prowl, od `1` do `5` w ntfy, wartości `info`/`warning`/`critical` w LaMetric, a dla Companion App na iOS jest to
  `interruption-level` pod `push`.
- **Niektóre usługi mają akcję na każde miejsce docelowe.** Stary styl Companion App tworzy akcję
  `notify.mobile_app_<device>` dla każdego telefonu, więc nazwa akcji jest miejscem docelowym. Automatyzacje wskazują
  telefon, a nie osobę, i trzeba je zmieniać przy wymianie telefonu.
- **Niektóre usługi mają dwa style naraz.** Nowsze integracje oferują encję notify, która działa z
  `notify.send_message`, obszarami, etykietami i grupami, ale wysyła tylko wiadomość i tytuł. Do wszystkiego innego
  dodają własną akcję skierowaną do tej samej encji, np. `smtp.send_message` lub `ntfy.publish`. Żeby wysłać obraz,
  trzeba porzucić wspólną akcję na rzecz własnej akcji integracji.
- **Mowa, dzwonki i komunikaty na ekranie to jeszcze coś innego.** `tts.speak`, `persistent_notification.create`,
  `alexa_devices.send_sound` i `mqtt.publish` mają każda własną postać i własne miejsca docelowe, i żadna z nich nie
  jest akcją notify.

Encje notify to właściwy kierunek: można je wskazywać według obszaru, etykiety i urządzenia, a w interfejsie
wyświetlają się poprawnie. Nie przenoszą jednak jeszcze niczego poza wiadomością i tytułem, a wiele integracji,
zwłaszcza SMS, jeszcze na nie nie przeszło.

## Style akcji powiadomień { #the-styles-of-notification-action }

### 1. Stara akcja notify dla usługi { #1-legacy-notify-action-for-a-service }

Jedna akcja dla każdej skonfigurowanej usługi, o wspólnej postaci: `message`, `title`, `target` i dowolne `data`.
Znaczenie `target` i klucze w `data` należą do danej integracji.

```yaml
action: notify.smtp
data:
  title: Front door
  message: The front door has been open for 10 minutes
  target:
    - anna@example.com
  data:
    images:
      - /config/www/snapshots/front_door.jpg
```

Ta sama akcja dla Twilio SMS przyjmuje numery telefonów jako `target` i `media_url` w `data`.

### 2. Stara akcja notify dla urządzenia { #2-legacy-notify-action-for-a-device }

Ta sama postać co w stylu 1, ale integracja tworzy akcję dla każdego urządzenia, więc miejsce docelowe jest w nazwie
akcji. Głównym przykładem jest Companion App, z `notify.mobile_app_<device>` dla każdego telefonu i różnymi kluczami
`data` dla iOS i Androida.

```yaml
action: notify.mobile_app_annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
  data:
    image: /api/camera_proxy/camera.front_door
    url: /lovelace/doors          # iOS
    clickAction: /lovelace/doors  # Android
    actions:
      - action: CLOSE_DOOR
        title: Close it
```

### 3. Encja notify z `notify.send_message` { #3-notify-entity-with-notifysend_message }

Jedna wspólna akcja dla wszystkich encji notify, którą można kierować według encji, urządzenia, obszaru lub etykiety,
w pełni obsługiwana przez edytor w interfejsie. Przyjmuje tylko `message` i `title`, a tytułu używają tylko encje,
które deklarują jego obsługę. Nie ma `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. Własna akcja integracji, skierowana do jej encji notify { #4-the-integrations-own-action-aimed-at-its-notify-entity }

Jako miejsce docelowe służy encja notify integracji, a integracja dodaje własną akcję z płaskimi polami na wszystko,
czego `notify.send_message` nie może wysłać. Pola różnią się w każdej integracji.

```yaml
action: ntfy.publish
target:
  entity_id: notify.ntfy_alerts
data:
  title: Front door
  message: The front door has been open for 10 minutes
  priority: 4
  click: https://my.home/lovelace/doors
  attach: https://my.home/local/snapshots/front_door.jpg
```

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` i akcje
`telegram_bot.send_*` działają tak samo, każda z innymi polami.

### 5. Własna akcja integracji, z własnymi miejscami docelowymi { #5-the-integrations-own-action-with-its-own-targets }

Akcje, które w ogóle nie opierają się na notify i wybierają miejsce docelowe po swojemu: urządzenie, pokój, topic
albo odtwarzacz multimediów razem z silnikiem TTS.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Inne to `lametric.message` (według `device_id`), `alexa_devices.send_sound` (według `device_id`),
`matrix.send_message` (według pokoju), `mqtt.publish` (według topicu) i `persistent_notification.create` (bez miejsca
docelowego, pojawia się w interfejsie Home Assistant).

### 6. Grupy { #6-groups }

Oba rodzaje grup powiadomień opisano [powyżej](#why-cant-i-just-use-a-group). Pomocnik Grupa powiadomień to encja
notify używana w stylu 3. Stara grupa notify to akcja stylu 1, która wywołuje inne akcje stylu 1 lub 2.

## Integracje i ich style { #integrations-and-their-styles }

Home Assistant 2026.11. **Oba** oznacza, że integracja ma dwa style, z których encja notify jest tym łatwym, a drugi
jest potrzebny do wszystkiego poza wiadomością i tytułem.

| Integracja              | Stara akcja (1 lub 2)                    | Encja notify (3)               | Własna akcja (4 lub 5)                           | Poza wiadomością i tytułem                        |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Oba**, na telefon            | -                                                | Stare `data`: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (e-mail)           | `notify.<name>`, `target` = adresy       | **Oba**, na odbiorcę           | `smtp.send_message` (4)                          | Stare `data.images`, `data.html`; własna akcja `html`, `attachments`, `priority` |
| Bot Telegram            | Usunięta w 2026.11                       | Tak, na czat                   | `telegram_bot.send_message`, `send_photo`, ... (4) | Własne akcje: `keyboard`, `inline_keyboard`, `parse_mode`, osobne akcje dla zdjęć i plików |
| Twilio SMS              | `notify.<name>`, `target` = numery       | Nie                            | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = numery       | Nie                            | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = numery       | Nie                            | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = urządzenia   | Nie                            | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = kanały       | Nie                            | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = ID kanałów  | **Oba**, na kanał, bez tytułu  | -                                                | Stare `data.images`, `data.embed`, `data.urls`    |
| Matrix                  | `notify.<name>`, `target` = pokoje       | Nie                            | `matrix.send_message` (5)                        | `data.images`                                     |
| Push HTML5              | `notify.<name>`, `target` = rejestracje  | **Oba**                        | `html5.send_message` (4)                         | Własna akcja: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Oba**                        | `ntfy.publish` (4)                               | Własna akcja: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, przestarzała            | **Oba**, bez tytułu            | `prowl.send_message` (4)                         | Własna akcja: `priority`, `url`                   |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Oba**                        | `nfandroidtv.send_message` (4)                   | Własna akcja: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Oba**, bez tytułu            | `lametric.message` według urządzenia (5)         | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | Nie (proponowana)              | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | Nie                            | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Oba**, mówienie i ogłaszanie na urządzenie | `alexa_devices.send_sound` według urządzenia (5) | Dźwięki tylko przez własną akcję |
| Zamiana tekstu na mowę  | `notify.<name>` (YAML `platform: tts`)   | Nie                            | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Trwałe powiadomienie    | `notify.persistent_notification`         | Nie                            | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Tak, bez tytułu                | `mqtt.publish` według topicu (5)                 | Dowolny payload                                   |

## Powiadamianie osoby, a nie urządzenia { #notifying-a-person-not-a-device }

Home Assistant wie, kim jest każda osoba i które lokalizatory urządzeń za nią podążają, ale nie wie, jak się z nią
skontaktować. Zespół Home Assistant pracuje nad tym po dyskusji społeczności „What the Heck?"
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), z propozycją
w [dyskusji architektonicznej #1552](https://github.com/home-assistant/architecture/discussions/1552): każda osoba
dostaje listę swoich encji notify, a `notify.send_message` można wysłać do `person.anna`. To rozwiązuje największy
codzienny problem, czyli wymianę telefonu w każdej automatyzacji, i czyni encje notify naturalnym sposobem
docierania do kogoś.

Supernotify będzie to obsługiwać tak szybko, jak to możliwe po wydaniu, zarówno wysyłając do osoby przez jej
powiązane encje notify, jak i pozwalając, by `notify.send_message` do osoby przechodziło przez własny routing
Supernotify.

## Co z tym robi Supernotify { #what-supernotify-does-about-it }

Supernotify bierze jedno powiadomienie z jednym zestawem opcji i zamienia je we właściwe wywołanie dla każdego
kanału:

- **Jedna akcja do wszystkiego.** `supernotify.notify` przyjmuje raz wiadomość, tytuł, obrazy, przyciski i priorytet,
  a każdy [transport](../../transports/index.md) przekłada to, co obsługuje jego kanał, na styl, nazwy pól i miejsca
  docelowe potrzebne jego integracji, czy to stara akcja, encja notify, własna akcja, czy TTS.
- **Osoby, nie urządzenia.** [Recipients](../../configuration/people.md) przechowują e-mail, numer telefonu, czat
  Telegram itd. każdej osoby, a ich telefony z Companion App są wykrywane automatycznie. Powiadom `person.anna`, a
  każdy kanał dostanie właściwy adres. Każdy recipient ma też własną encję notify.
- **Kto ma je dostać.** Powiadomienia mogą trafiać tylko do osób w domu albo tylko do nieobecnych, a w razie potrzeby
  przechodzić na inne kanały lub osoby. Zobacz przepis
  [Routing według obecności z rezerwą](../../recipes/presence_routing_with_fallback.md).
- **Czego dotyczą.** [Scenarios](../../configuration/scenarios.md) i priorytety decydują, których kanałów użyć, więc
  wiadomość o niskim priorytecie może trafić tylko na telefon, a krytyczna także uruchomi dzwonki i zostanie
  wypowiedziana przez głośniki.
- **Nie za często.** [Drzemka](../../usage/snoozing.md) i
  [wykrywanie duplikatów](../../configuration/dupe_detection.md) zapobiegają powtarzaniu tego samego alertu.
