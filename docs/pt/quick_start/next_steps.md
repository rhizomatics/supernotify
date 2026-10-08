---
title: O que fazer a seguir
tags:
  - quickstart
  - automation
  - dashboard
  - recipes
description: O que fazer depois da primeira notificação do Supernotify - notificar a partir de uma automação, adicionar um dashboard, escolher quem e o que é notificado, e encontrar ideias nas receitas
---
# O que fazer a seguir

Comece por uma automação, pois é para isso que servem as notificações. O resto é opcional e pode ser feito por qualquer ordem.

## Adicionar uma notificação a uma automação { #add-a-notification-to-an-automation }

`supernotify.notify` é uma ação como qualquer outra, por isso entra em uma automação da forma habitual. Este exemplo envia uma notificação quando um sensor de movimento no corredor dispara.

Crie uma automação com o sensor de movimento como gatilho, depois escolha **Adicionar ação** e procure Supernotify:

![Selecionar a ação](../../assets/images/add_action_automation.png){width=600}

Preencha a mensagem e tudo o mais que você quiser da [sua primeira notificação](first_notification.md), como um destino ou uma delivery:

![Configurar a ação](../../assets/images/automation_action_simple.png){width=600}

```yaml title="Automação com sensor de movimento"
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

Para ouvi-la também nos alto-falantes, adicione `alexa_devices_announce_all` e `mobile_push` como deliveries. [Enviar notificações](../../usage/notifying.md) descreve tudo o resto que a ação consegue fazer.

Para um exemplo mais completo, com anúncios de voz e uma imagem da câmera, veja a receita [Tem alguém na porta](../../recipes/someone_at_the_door.md).

## Adicionar um dashboard { #add-a-dashboard }

O [Supernotify Cards](https://github.com/lollox80/supernotify-cards) tem muitos cartões específicos para controlar e monitorar notificações, enviá-las manualmente ou testar configurações.

![Cartões de resumo e de transport](../../assets/images/cards.png)

A página [Dashboard](../../configuration/dashboard.md) tem um exemplo completo para colar em um novo dashboard, que depois pode ser editado visualmente.

## Ligar e desligar pessoas e deliveries { #switch-people-and-deliveries-on-and-off }

Cada pessoa que o Supernotify conhece tem uma entidade `switch` no Home Assistant, e cada delivery também. Desligue uma para não incomodar alguém, ou para silenciar os alto-falantes por algum tempo, sem alterar nenhuma automação.

## Notificar apenas alguns dispositivos { #notify-just-some-devices }

Os destinos podem ser uma **Área**, um **Andar** ou uma **Etiqueta**, além de uma pessoa ou um dispositivo, por isso uma notificação pode ir para os alto-falantes do térreo, ou para tudo o que tem a etiqueta da cozinha. Veja [Targets](../../usage/targets.md) e as [perguntas frequentes](../../faqs.md).

## Ajustar as configurações { #tune-the-settings }

O arquivo, a detecção de duplicados e a manutenção podem ser alterados na opção **Configurar** da integração, em **Configurações → Dispositivos e serviços**. Veja [Arquivo](../../configuration/archiving.md) e [Detecção de duplicados](../../configuration/dupe_detection.md).

## Inspire-se { #be-inspired }

Você encontra muitas ideias com configuração de exemplo nas [receitas](../../recipes/index.md).

## Ir mais longe com YAML { #go-further-with-yaml }

Com alguma configuração YAML é possível fazer mais, e tudo isto é opcional:

- Dar às pessoas um endereço de e-mail ou um número de telefone, em [People](../../configuration/people.md)
- Criar suas próprias deliveries, como um e-mail HTML ou um conjunto fixo de alto-falantes, em [Deliveries](../../configuration/deliveries.md)
- Mudar o comportamento das notificações à noite, ou quando não há ninguém em casa, com [Scenarios](../../configuration/scenarios.md)
- Anexar capturas de câmeras, em [Multimedia](../../configuration/multimedia.md)

[Conceitos avançados](advanced_concepts.md) explica as ideias por trás disto, e [Configuração](../../configuration/index.md) é a referência.

## Obter ajuda { #get-help }

Pergunte na página [Discussions](https://github.com/rhizomatics/supernotify/discussions), ou use um agente de IA - veja a última resposta nas [perguntas frequentes](../../faqs.md).
