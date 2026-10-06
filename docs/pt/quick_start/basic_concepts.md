---
title: Conceitos básicos
tags:
  - quickstart
  - delivery
  - target
  - recipient
  - priority
description: Os poucos conceitos do Supernotify necessários para começar - destinos, recipients, deliveries e prioridade, e como se encaixam
---
# Conceitos básicos

## Como tudo se encaixa { #how-it-fits-together }

Uma única notificação de uma automação pode transformar-se em várias notificações diferentes, cada uma adaptada à forma como é enviada.

![Uma notificação de uma automação torna-se um e-mail, dois alertas push, um SMS e um anúncio em um alto-falante](../../assets/images/concepts_flow.svg)

Lendo a imagem da esquerda para a direita:

1. **Quem notificar** - os [destinos](#target). As pessoas são convertidas nas formas de contatá-las, usando seus dados de [recipient](#recipient)
2. **Delivery** - são escolhidas as [deliveries](#delivery) aplicáveis, por padrão ou porque você as pediu
3. **Notificações** - cada delivery escolhe os destinos que pode usar e envia uma notificação adequada, de modo que um e-mail pode ter um layout HTML completo com imagens, enquanto o alto-falante da cozinha recebe uma curta mensagem falada

Três palavras cobrem quase tudo em uma instalação feita apenas pela interface.

## Destino (target) { #target }

Um destino é **quem ou o que é notificado**: uma pessoa, um celular, um alto-falante, um endereço de e-mail, ou uma área, um andar ou uma etiqueta que representa vários dispositivos.

Sem destinos indicados, a notificação segue para todos.

## Recipient { #recipient }

Um recipient é **uma pessoa, tal como o Supernotify a conhece**: seus celulares e tablets e, opcionalmente, um endereço de e-mail e um número de telefone. Os recipients são encontrados automaticamente a partir das entidades *Person* do Home Assistant.

Um recipient não é outro tipo de destino. Uma pessoa é uma das coisas que um destino pode ser, e o recipient é onde o Supernotify procura como contatá-la. É por isso que `person.joe_mctest` funciona como destino, e você não precisa do endereço de e-mail do Joe em cada automação.

## Delivery { #delivery }

Uma delivery é **uma forma de enviar uma notificação**, com um nome, como `mobile_push`, `email` ou `alexa_devices_announce_all`. O Supernotify cria deliveries para tudo o que encontra no seu Home Assistant, e são elas que aparecem na caixa **Delivery** da ação `supernotify.notify`.

Sem deliveries indicadas, o Supernotify usa as que conseguem descobrir sozinhas para onde enviar, como as notificações push e o e-mail.

## Prioridade { #priority }

A prioridade indica **quão urgente é uma notificação**, em cinco níveis: `minimum`, `low`, `medium`, `high` e `critical`. É opcional, e vale `medium` se não for indicada. A prioridade é passada aos celulares, programas de e-mail e a tudo o que a entenda.

## Mais dois, para depois { #two-more-for-later }

Aparecem por toda a documentação, e nenhum é necessário para começar.

- Um **transport** é o meio técnico por trás de uma delivery, normalmente uma integração do Home Assistant como o aplicativo móvel, SMTP ou Alexa Devices. Uma delivery é um transport mais as configurações a usar com ele, por isso um transport pode ter várias deliveries, como um `email` simples e um `html_email`.
- Um **scenario** é um pacote de configurações com um nome, que muda as deliveries usadas e a forma como se comportam, por exemplo mais discretas à noite. Os scenarios configuram-se em YAML.

[Conceitos avançados](advanced_concepts.md) trata de ambos, e do resto que a configuração YAML permite.
