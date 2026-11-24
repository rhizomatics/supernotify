---
title: Perché le notifiche sono difficili
tags:
  - principles
  - notify_entity
  - mobile_push
  - email
  - sms
  - telegram
description: Perché in Home Assistant è difficile inviare una stessa notifica via e-mail, Telegram, push mobile e SMS, con un catalogo dei diversi stili di azione di notifica e di come li usa ogni integrazione
---
# Perché le notifiche sono difficili in Home Assistant

Questa pagina spiega perché inviare un messaggio su più canali in Home Assistant è più difficile di quanto sembri. È
il motivo per cui esiste Supernotify, ed è anche pensata come contributo al lavoro in corso in Home Assistant per
rendere le notifiche più semplici. Descrive Home Assistant **2026.11**, verificato sul codice sorgente. Ogni versione
porta altre integrazioni alle entità notify, quindi alcune righe della [tabella](#integrations-and-their-styles)
cambieranno.

## "Perché non posso usare semplicemente un gruppo?" { #why-cant-i-just-use-a-group }

Supponiamo che un avviso debba raggiungere il tuo telefono, la tua e-mail, una chat di famiglia su Telegram e, via SMS,
qualcuno senza smartphone. Home Assistant ha i gruppi di notifica, quindi sembra naturale creare un gruppo con questi
quattro e inviare a quello. Esistono due tipi di gruppo di notifica, e nessuno dei due può contenerli tutti e quattro.

**L'aiutante Gruppo di notifica**, creato dall'interfaccia, raggruppa **entità notify** e invia con
`notify.send_message`. La Companion App, SMTP e il bot Telegram hanno entità notify, quindi tre dei quattro possono
entrarci. L'SMS no: le integrazioni SMS, come Twilio SMS e ClickSend, hanno solo il vecchio stile di azione notify.
Il gruppo invia solo `message` e `title`, e toglie il titolo a tutti se un membro non supporta i titoli. Non c'è modo
di aggiungere un'istantanea della telecamera, un pulsante nella notifica del telefono, un corpo e-mail in HTML o
altro.

**Il vecchio gruppo notify**, solo in YAML, raggruppa le vecchie **azioni notify**, come
`notify.mobile_app_annas_phone` o `notify.smtp`. Telegram non può entrarci, perché la sua azione notify è stata
rimossa nella 2026.11 ed è rimasta solo l'entità notify. Gli altri tre sì, ma ogni membro riceve la stessa chiamata:

- `target` significa una cosa diversa per ciascuno: indirizzi e-mail per SMTP e numeri di telefono per Twilio, mentre
  l'azione propria di un telefono lo ignora. Un solo `target` non può andare bene per tutti.
- `data` viene inviato a ogni membro, qualunque siano le sue chiavi. Un'immagine è `data.image` per la Companion App,
  `data.images` (un elenco di file locali) per SMTP e `data.media_url` per Twilio SMS. Ogni membro riceve anche le
  chiavi pensate per gli altri, oltre alle proprie.
- Ogni membro può avere `data` fissi nel YAML, ma non dati che cambiano a ogni notifica, come un'immagine per questo
  avviso.

Nessuno dei due tipi di gruppo sa chi sta notificando. Quando si sostituisce un telefono, bisogna modificare il
gruppo. Se qualcuno è fuori casa, o il messaggio deve arrivare solo a chi è in casa, il gruppo non può deciderlo. I
gruppi sono solo elenchi fissi di destinazioni.

## Perché è così { #why-its-like-this }

Non è colpa di nessuno. In dieci anni Home Assistant ha aggiunto centinaia di integrazioni di notifica, ognuna con le
esigenze del proprio servizio, e la parte comune delle notifiche è sempre stata molto piccola:

- **Solo `message` è comune.** `title` è comune alla maggior parte delle azioni. `target` esiste in uno stile e non
  negli altri, e significa una cosa diversa in ogni integrazione. Tutto il resto (immagini, pulsanti, priorità, suono,
  HTML, allegati, azioni al tocco) va sotto una chiave `data` libera nel vecchio stile, oppure nei campi di un'azione
  propria dell'integrazione nello stile nuovo. Nessuno schema comune li copre.
- **La stessa idea ha nomi diversi.** Un'azione al tocco è `data.url` su iOS ma `data.clickAction` su Android,
  entrambe nella Companion App. È `click` in ntfy e `url` in Prowl e Pushover. La priorità va da `-2` a `2` in
  Pushover e Prowl, da `1` a `5` in ntfy, è `info`/`warning`/`critical` in LaMetric, ed è `interruption-level` sotto
  `push` per la Companion App iOS.
- **Alcuni servizi hanno un'azione per destinazione.** Il vecchio stile della Companion App crea un'azione
  `notify.mobile_app_<device>` per ogni telefono, quindi il nome dell'azione è la destinazione. Le automazioni nominano
  il telefono, non la persona, e vanno modificate quando si sostituisce il telefono.
- **Alcuni servizi hanno due stili insieme.** Le integrazioni più recenti offrono un'entità notify, che funziona con
  `notify.send_message`, aree, etichette e gruppi, ma invia solo messaggio e titolo. Per tutto il resto aggiungono
  un'azione propria rivolta alla stessa entità, come `smtp.send_message` o `ntfy.publish`. Per usare un'immagine
  bisogna lasciare l'azione comune e passare a quella propria dell'integrazione.
- **Voce, campanelli e messaggi a schermo sono ancora a parte.** `tts.speak`, `persistent_notification.create`,
  `alexa_devices.send_sound` e `mqtt.publish` hanno ognuna la propria forma e le proprie destinazioni, e nessuna è
  un'azione notify.

Le entità notify sono la direzione giusta: si possono indirizzare per area, etichetta e dispositivo, e compaiono
correttamente nell'interfaccia. Però non trasportano ancora nulla oltre a messaggio e titolo, e molte integrazioni,
soprattutto quelle SMS, non sono ancora passate a esse.

## Gli stili di azione di notifica { #the-styles-of-notification-action }

### 1. Vecchia azione notify per un servizio { #1-legacy-notify-action-for-a-service }

Un'azione per ogni servizio configurato, con una forma comune: `message`, `title`, `target` e un `data` libero. Il
significato di `target` e le chiavi di `data` dipendono da ogni integrazione.

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

La stessa azione per Twilio SMS accetta numeri di telefono come `target` e `media_url` in `data`.

### 2. Vecchia azione notify per un dispositivo { #2-legacy-notify-action-for-a-device }

Stessa forma dello stile 1, ma l'integrazione crea un'azione per dispositivo, quindi la destinazione è nel nome
dell'azione. L'esempio principale è la Companion App, con `notify.mobile_app_<device>` per ogni telefono e chiavi
`data` diverse per iOS e Android.

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

### 3. Entità notify con `notify.send_message` { #3-notify-entity-with-notifysend_message }

Un'azione comune a tutte le entità notify, che si può indirizzare per entità, dispositivo, area o etichetta, ed è
pienamente supportata dall'editor dell'interfaccia. Accetta solo `message` e `title`, e il titolo è usato solo dalle
entità che dichiarano di supportarlo. Non c'è `data`.

```yaml
action: notify.send_message
target:
  entity_id: notify.annas_phone
data:
  title: Front door
  message: The front door has been open for 10 minutes
```

### 4. L'azione propria dell'integrazione, rivolta alla sua entità notify { #4-the-integrations-own-action-aimed-at-its-notify-entity }

Come destinazione si usa l'entità notify dell'integrazione, e l'integrazione aggiunge un'azione propria con campi
piatti per tutto ciò che `notify.send_message` non può inviare. I campi cambiano da un'integrazione all'altra.

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

`smtp.send_message`, `html5.send_message`, `prowl.send_message`, `nfandroidtv.send_message` e le azioni
`telegram_bot.send_*` funzionano allo stesso modo, ognuna con campi diversi.

### 5. L'azione propria dell'integrazione, con destinazioni proprie { #5-the-integrations-own-action-with-its-own-targets }

Azioni che non si basano affatto su notify e scelgono la destinazione a modo loro: un dispositivo, una stanza, un
topic, o un lettore multimediale insieme a un motore TTS.

```yaml
action: tts.speak
target:
  entity_id: tts.home_assistant_cloud
data:
  media_player_entity_id: media_player.kitchen
  message: The front door has been open for 10 minutes
```

Altre sono `lametric.message` (per `device_id`), `alexa_devices.send_sound` (per `device_id`), `matrix.send_message`
(per stanza), `mqtt.publish` (per topic) e `persistent_notification.create` (senza destinazione, compare
nell'interfaccia di Home Assistant).

### 6. Gruppi { #6-groups }

I due tipi di gruppo di notifica sono descritti [sopra](#why-cant-i-just-use-a-group). L'aiutante Gruppo di notifica
è un'entità notify usata con lo stile 3. Il vecchio gruppo notify è un'azione dello stile 1 che chiama altre azioni
dello stile 1 o 2.

## Le integrazioni e i loro stili { #integrations-and-their-styles }

Home Assistant 2026.11. **Entrambi** significa che l'integrazione ha due stili: l'entità notify è quello semplice e
l'altro serve per tutto ciò che va oltre messaggio e titolo.

| Integrazione            | Vecchia azione (1 o 2)                   | Entità notify (3)              | Azione propria (4 o 5)                           | Oltre messaggio e titolo                          |
| ----------------------- | ---------------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------------------------------------- |
| Companion App           | `notify.mobile_app_<device>` (2)         | **Entrambi**, per telefono     | -                                                | Vecchio `data`: `image`, `actions`, `url` (iOS), `clickAction` (Android), `push` |
| SMTP (e-mail)           | `notify.<name>`, `target` = indirizzi    | **Entrambi**, per destinatario | `smtp.send_message` (4)                          | Vecchia `data.images`, `data.html`; azione propria `html`, `attachments`, `priority` |
| Bot Telegram            | Rimossa nella 2026.11                    | Sì, per chat                   | `telegram_bot.send_message`, `send_photo`, ... (4) | Azioni proprie: `keyboard`, `inline_keyboard`, `parse_mode`, azioni separate per foto e file |
| Twilio SMS              | `notify.<name>`, `target` = numeri       | No                             | -                                                | `data.media_url`                                  |
| ClickSend               | `notify.<name>`, `target` = numeri       | No                             | -                                                | -                                                 |
| Signal Messenger        | `notify.<name>`, `target` = numeri       | No                             | -                                                | `data.attachments`, `data.urls`, `data.text_mode` |
| Pushover                | `notify.<name>`, `target` = dispositivi  | No                             | -                                                | `data.priority`, `sound`, `url`, `attachment`, `html`, ... |
| Slack                   | `notify.<name>`, `target` = canali       | No                             | -                                                | `data.blocks`, `data.file`                        |
| Discord                 | `notify.discord`, `target` = ID canale   | **Entrambi**, per canale, senza titolo | -                                        | Vecchia `data.images`, `data.embed`, `data.urls`  |
| Matrix                  | `notify.<name>`, `target` = stanze       | No                             | `matrix.send_message` (5)                        | `data.images`                                     |
| Push HTML5              | `notify.<name>`, `target` = registrazioni | **Entrambi**                  | `html5.send_message` (4)                         | Azione propria: `image`, `icon`, `actions`, `urgency`, `ttl`, ... |
| ntfy                    | -                                        | **Entrambi**                   | `ntfy.publish` (4)                               | Azione propria: `priority`, `tags`, `click`, `attach`, `actions`, ... |
| Prowl                   | `notify.<name>`, deprecata               | **Entrambi**, senza titolo     | `prowl.send_message` (4)                         | Azione propria: `priority`, `url`                 |
| Notifications for Android TV / Fire TV | `notify.<name>`           | **Entrambi**                   | `nfandroidtv.send_message` (4)                   | Azione propria: `image`, `icon`, `duration`, `position`, ... |
| LaMetric                | `notify.<name>`                          | **Entrambi**, senza titolo     | `lametric.message` per dispositivo (5)           | `icon`, `sound`, `cycles`, `priority`             |
| Kodi                    | `notify.<name>`                          | No (proposta)                  | -                                                | `data.icon`, `data.displaytime`                   |
| LG webOS TV             | `notify.<tv>`                            | No                             | -                                                | `data.icon`                                       |
| Alexa Devices           | -                                        | **Entrambi**, parlare e annunciare per dispositivo | `alexa_devices.send_sound` per dispositivo (5) | Suoni solo con l'azione propria |
| Sintesi vocale          | `notify.<name>` (YAML `platform: tts`)   | No                             | `tts.speak` (5)                                  | `media_player_entity_id`, `language`, `options`   |
| Notifica persistente    | `notify.persistent_notification`         | No                             | `persistent_notification.create` (5)             | `notification_id`                                 |
| MQTT                    | -                                        | Sì, senza titolo               | `mqtt.publish` per topic (5)                     | Qualsiasi payload                                 |

## Notificare una persona, non un dispositivo { #notifying-a-person-not-a-device }

Home Assistant sa chi è ogni persona e quali tracker di dispositivi la seguono, ma non come raggiungerla. Il team di
Home Assistant ci sta lavorando, dopo la discussione della community "What the Heck?"
[Notifying people is hard](https://community.home-assistant.io/t/wth-notifying-people-is-hard/1030879), con una
proposta nella [discussione di architettura #1552](https://github.com/home-assistant/architecture/discussions/1552):
ogni persona ha un elenco delle proprie entità notify, e `notify.send_message` può essere inviato a `person.anna`.
Questo risolve il problema quotidiano più grande, cioè sostituire il telefono in ogni automazione, e fa delle entità
notify il modo naturale per raggiungere qualcuno.

Supernotify lo supporterà il prima possibile una volta rilasciato, sia inviando a una persona tramite le sue entità
notify collegate, sia permettendo che `notify.send_message` verso una persona passi per l'instradamento di
Supernotify.

## Cosa fa Supernotify { #what-supernotify-does-about-it }

Supernotify prende una notifica, con un unico insieme di opzioni, e la trasforma nella chiamata giusta per ogni
canale:

- **Un'azione per tutto.** `supernotify.notify` riceve una volta sola messaggio, titolo, immagini, pulsanti e
  priorità, e ogni [transport](../../transports/index.md) adatta ciò che il suo canale supporta allo stile, ai nomi
  dei campi e alle destinazioni che servono alla sua integrazione, che sia vecchia azione, entità notify, azione
  propria o TTS.
- **Persone, non dispositivi.** I [recipient](../../configuration/people.md) contengono e-mail, numero di telefono,
  chat Telegram e così via di ogni persona, e i loro telefoni con la Companion App vengono trovati automaticamente.
  Notifica `person.anna` e ogni canale riceve l'indirizzo giusto. Ogni recipient ha anche una propria entità notify.
- **Chi deve riceverla.** Le notifiche possono andare solo a chi è in casa, o solo a chi è fuori, e ripiegare su
  altri canali o altre persone. Vedi la ricetta
  [Instradamento per presenza con ripiego](../../recipes/presence_routing_with_fallback.md).
- **Di cosa si tratta.** Gli [scenario](../../configuration/scenarios.md) e le priorità decidono quali canali usare,
  così un messaggio a bassa priorità può andare solo al telefono, mentre uno critico fa anche suonare i campanelli e
  viene annunciato dagli altoparlanti.
- **Non troppo spesso.** La [posticipazione](../../usage/snoozing.md) e il
  [rilevamento dei duplicati](../../configuration/dupe_detection.md) evitano che lo stesso avviso si ripeta.
