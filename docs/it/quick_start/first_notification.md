---
title: Invia la tua prima notifica
tags:
  - quickstart
  - developer tools
  - notification
description: Invia una prima notifica Supernotify da Home Assistant - a tutti, a una persona e agli altoparlanti Alexa
---
# Invia la tua prima notifica

Tutto ciò che è in questa pagina si fa dall'interfaccia di Home Assistant, subito dopo l'[installazione](installation.md). Ogni passaggio mostra anche lo YAML, per chi lo preferisce.

## 1. Notificare tutti { #1-notify-everyone }

Apri la [scheda Azioni](https://www.home-assistant.io/docs/tools/dev-tools/#actions-tab) negli **Strumenti per sviluppatori**, scegli l'azione `supernotify.notify`, scrivi un messaggio e premi **Esegui azione**.

![Azione negli strumenti per sviluppatori](../../assets/images/tools_action_notify.png){width=600}

```yaml title="Messaggio a tutti"
action: supernotify.notify
data:
  message: Something went off in the basement
```

A una notifica basta un messaggio. Senza altre indicazioni, arriva a ogni telefono e tablet con l'app di Home Assistant, per tutti in casa.

## 2. Notificare una persona { #2-notify-one-person }

Probabilmente sono più persone di quante ne vuoi. Per limitare, scegli entità `person`, o singoli dispositivi mobili, come **destinazioni** (target):

![Notificare tutti i dispositivi mobili di una persona](../../assets/images/person_notify.png){width=400}

```yaml title="Messaggio a una persona"
action: supernotify.notify
data:
  message: Something went off in the basement
  target: person.john_mcdoe
```

Ora la ricevono solo i dispositivi di John. Scegliere una persona invece di un telefono fa sì che la notifica arrivi ancora quando John cambia telefono.

## 3. Scegliere come viene inviata { #3-choose-how-its-sent }

La casella **Delivery** elenca i modi che Supernotify ha trovato per inviare notifiche. Se la lasci vuota, sceglie Supernotify; se ne scegli alcune, vengono usate solo quelle.

![Selezione della delivery](../../assets/images/delivery_choice.png)

Se hai dispositivi Alexa, usa `alexa_devices_announce_all` o `alexa_devices_speak_all`. (Announce aggiunge un segnale acustico iniziale, speak no.) Puoi combinarle con e-mail e notifiche sull'app mobile in un'unica notifica.

```yaml title="Altoparlanti e telefoni insieme"
action: supernotify.notify
data:
  message: Someone is at the front door
  delivery:
    - alexa_devices_announce_all
    - mobile_push
```

Ognuna riceve una notifica adatta, così gli altoparlanti pronunciano il messaggio mentre i telefoni lo mostrano.

Quando funziona, il passo successivo è [aggiungere una notifica a un'automazione](next_steps.md#add-a-notification-to-an-automation).
