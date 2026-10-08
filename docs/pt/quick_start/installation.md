---
title: Instalação
tags:
  - installation
  - hacs
  - configuration
  - quickstart
description: Instale o Supernotify para Home Assistant pelo HACS e configure-o pela interface, sem YAML
---

# Instalação

## Instalar pelo HACS { #install-from-hacs }

Primeiro, confirme que o **HACS** está instalado.

Se não estiver, consulte as [instruções do HACS](https://hacs.xyz/docs/use/). O Supernotify é um dos repositórios padrão do HACS, por isso não é preciso configurar um repositório personalizado.

Na página do HACS no Home Assistant, selecione **Supernotify** na lista de integrações disponíveis, baixe-o e reinicie o Home Assistant.

![Seleção no HACS](../../assets/images/hacs_select.png){width=400}

## Adicionar a integração { #add-the-integration }

Vá a **Configurações → Dispositivos e serviços → Adicionar integração** e procure **Supernotify**. Aceite os valores padrão.

![Adicionar a integração](../../assets/images/new_integration.png)

## Detecção e valores padrão { #discovery-and-defaults }

Isto é tudo o que é preciso para ter as primeiras notificações a funcionar.

O Supernotify olha para o que já existe no Home Assistant e encontra:

- **Pessoas** - todos os que têm uma *Pessoa* ou um *Usuário* no Home Assistant, e os celulares ou tablets em que usam o aplicativo do Home Assistant
- **Formas de notificar** - notificações push no celular, uma integração de e-mail SMTP existente, quaisquer entidades notify e dispositivos como alto-falantes Alexa ou campainhas, se você os tiver

Cria uma *delivery* para cada forma de notificar que encontra, além de algumas de conveniência, como `chime_siren_all` e `alexa_devices_announce_all`, se você tiver esses dispositivos.

O arquivo, a detecção de duplicados e as configurações de manutenção podem ser ajustados depois, na opção **Configurar** da integração.

Agora [envie sua primeira notificação](first_notification.md).
