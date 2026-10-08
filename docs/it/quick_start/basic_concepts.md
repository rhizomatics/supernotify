---
title: Concetti di base
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: I pochi concetti di Supernotify che servono per iniziare - destinazioni, recipient, delivery e priorità, e come si combinano
---
# Concetti di base

## Come si combina il tutto { #how-it-fits-together }

Una sola notifica da un'automazione può trasformarsi in più notifiche diverse, ognuna adattata al modo in cui viene inviata.

![Una notifica da un'automazione diventa un'e-mail, due notifiche push, un SMS e un annuncio da un altoparlante](../../assets/images/concepts_flow.svg)

Leggendo l'immagine da sinistra a destra:

1. **Chi notificare** - le [destinazioni](#target). Le persone vengono trasformate nei modi in cui possono essere raggiunte, usando i loro dati di [recipient](#recipient)
2. **Delivery** - vengono scelte le [delivery](#delivery) pertinenti, per impostazione predefinita o perché le hai richieste
3. **Notifiche** - ogni delivery prende le destinazioni che può usare e invia una notifica adatta, così un'e-mail può avere un layout HTML completo con immagini, mentre l'altoparlante della cucina riceve un breve messaggio vocale

Tre parole coprono quasi tutto in un'installazione fatta solo dall'interfaccia.

## Destinazione (target) { #target }

Una destinazione è **chi o cosa riceve la notifica**: una persona, un telefono, un altoparlante, un indirizzo e-mail, oppure un'area, un piano o un'etichetta che rappresenta più dispositivi.

Senza destinazioni, la notifica arriva a tutti.

## Recipient { #recipient }

Un recipient è **una persona, così come la conosce Supernotify**: i suoi telefoni e tablet e, facoltativamente, un indirizzo e-mail e un numero di telefono. I recipient vengono trovati automaticamente dalle entità *Person* di Home Assistant.

Un recipient non è un altro tipo di destinazione. Una persona è una delle cose che una destinazione può essere, e il recipient è dove Supernotify cerca come raggiungerla. Ecco perché `person.joe_mctest` funziona come destinazione, e non serve l'indirizzo e-mail di Joe in ogni automazione.

## Delivery { #delivery }

Una delivery è **un modo di inviare una notifica**, con un nome, come `mobile_push`, `email` o `alexa_devices_announce_all`. Supernotify crea delivery per tutto ciò che trova nel tuo Home Assistant, e sono quelle che compaiono nella casella **Delivery** dell'azione `supernotify.notify`.

Senza indicare delivery, Supernotify usa quelle che sanno capire da sole dove inviare, come le notifiche push e l'e-mail.

## Priorità { #priority }

La priorità indica **quanto è urgente una notifica**, su cinque livelli: `minimum`, `low`, `medium`, `high` e `critical`. È facoltativa, e vale `medium` se non indicata. La priorità viene passata ai telefoni, ai programmi di posta e a tutto ciò che la comprende.

## Altri due, per dopo { #two-more-for-later }

Compaiono in tutta la documentazione, e nessuno dei due serve per iniziare.

- Un **transport** è il mezzo tecnico dietro una delivery, di solito un'integrazione di Home Assistant come l'app mobile, SMTP o Alexa Devices. Una delivery è un transport più le impostazioni con cui usarlo, quindi un transport può avere più delivery, come una semplice `email` e una `html_email`.
- Uno **scenario** è un pacchetto di impostazioni con un nome, che cambia quali delivery vengono usate e come si comportano, ad esempio più discrete di notte. Gli scenario si configurano in YAML.

[Concetti avanzati](advanced_concepts.md) li tratta entrambi, insieme al resto di ciò che la configurazione YAML permette.
