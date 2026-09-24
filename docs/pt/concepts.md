---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - principles
description: Conceitos fundamentais do Supernotify para Home Assistant, incluindo Transport, Delivery, Scenario e Recipient
---
# Conceitos fundamentais

## Como tudo se encaixa { #how-it-fits-together }

Uma única notificação de uma automação pode se transformar em várias notificações diferentes, cada uma adaptada
à forma como é enviada.

![Uma notificação de uma automação vira um e-mail, dois alertas push, um SMS e um anúncio em um alto-falante](../assets/images/concepts_flow.svg)

1. **Destinos** - as pessoas são convertidas nas formas de contatá-las, usando seus dados de [Recipient](#recipient)
2. **Deliveries** - são escolhidas as [Deliveries](#delivery) aplicáveis, por padrão ou por meio de [Scenarios](#scenario)
3. **Notificações** - cada delivery pega os destinos que pode usar e envia uma notificação adequada,
   assim um e-mail pode ter um layout HTML completo com imagens, enquanto o alto-falante da cozinha recebe uma breve mensagem falada

## Destino (Target) { #target }
- Quem ou o que recebe a notificação, e como
  - Destinos *diretos*
    - endereço de e-mail
    - número de telefone
    - `entity_id` ou `device_id`, por exemplo para fazer um anúncio em um dispositivo Alexa
    - um ID personalizado para um transporte especializado como o Telegram
  - Destinos *indiretos*, que podem ser convertidos em destinos diretos
    - `person_id` para usar os recursos de *Recipient*
    - os seletores de destino padrão do Home Assistant, `label_id`, `floor_id` e `area_id`
    - destinos de *grupo* (grupos do Home Assistant novos e antigos)
- Os destinos podem ser qualificados com uma **Categoria de destino** específica, como `discord_channel:839439434`; veja [Prefixos de categoria](../usage/targets.md#category-prefixes)
- Cada destino é retirado da lista pela integração mais adequada para tratá-lo
  - Por exemplo, uma entidade Notify do Alexa Devices é tratada pelo transporte Alexa Devices, enquanto uma entidade Notify genérica recorre ao transporte Notify Entity, menos completo
- Veja [Targets](../usage/targets.md) para mais informações

## Destinatário (Recipient) { #recipient }
- Uma pessoa, com endereço de e-mail, número de telefone, dispositivos móveis ou destinos personalizados opcionais
  - Por padrão, descobertos automaticamente a partir das contas de usuário e entidades de pessoa já existentes no Home Assistant
- Facilita referir-se a pessoas nas automações: use `person.joe_mctest` em vez de lembrar o e-mail do Joe em cada notificação. Também funciona para números de telefone, se houver uma integração de SMS compatível, ou para identificadores personalizados como Telegram ou Discord
- Cada destinatário também tem uma entidade `switch` do Home Assistant, para ser fácil poupar alguém das notificações
- Veja [People](../configuration/people.md) e [Recipes](../recipes/index.md) para mais detalhes

## Transporte (Transport) { #transport }

- Um *transporte* é o meio técnico de notificar, geralmente usando uma das integrações do Home Assistant já instaladas
- Os *adaptadores de transporte* são o que diferencia o Supernotify dos grupos Notify comuns
  - Um grupo Notify parece permitir notificações multicanal com facilidade, mas na prática cada transporte tem estruturas `data` diferentes (e `data` dentro de `data`!), endereçamento etc., então no fim as notificações precisam ser reduzidas ao mínimo denominador comum, como apenas `message`!
- O Supernotify já vem com adaptadores para transportes comuns, como e-mail, push móvel, SMS e Alexa, além de um adaptador *Generic* que pode envolver qualquer outra ação do Home Assistant
- O adaptador de transporte permite enviar uma única notificação para muitas plataformas, mesmo quando têm interfaces diferentes e incompatíveis entre si
- Ele adapta as notificações ao transporte, removendo atributos que não são aceitos, reorganizando estruturas `data`, selecionando apenas os destinos apropriados e permitindo ajustes adicionais quando possível
- Cada transporte tem uma configuração padrão que permite muitos ajustes e valores padrão, evitando repetir os mesmos valores em cada notificação
- Veja [Transports](../transports/index.md) para mais detalhes

## Entrega (Delivery) { #delivery }

- Uma **Delivery** define cada canal de notificação que você quer usar
  - De fábrica, cada transporte tem uma delivery com o mesmo nome, por exemplo `email` ou `mobile_push`
  - Alguns transportes criam automaticamente deliveries adicionais, como `alexa_devices_announce_all` ou `chime_siren_all`
  - Com YAML é possível criar mais deliveries, por exemplo `html_email` além do `email` em texto simples, ou deliveries diferentes para assistentes de voz específicos
- Os transportes que conseguem selecionar destinos de forma inequívoca, como e-mail, push móvel, SMS, Alexa Devices e Notify Entity, são incluídos por padrão no tratamento dos destinos
  - Os outros podem ser incluídos pela configuração, usando Scenarios ou pedindo por eles em uma notificação
- Você pode definir suas próprias deliveries, com o nome que quiser, e ter várias para um mesmo transporte, por exemplo `plain_email` e `html_email`
- O [transporte Generic](../transports/generic.md) funciona como uma *caixa de ferramentas* para criar uma delivery para quase tudo o que o Home Assistant pode fazer e que ainda não é coberto por um transporte padrão
- Veja [Deliveries](../configuration/deliveries.md) e [Recipes](../recipes/index.md) para mais detalhes

## Cenário (Scenario) { #scenario }
- Um pacote de configurações que pode ser ativado pelo nome, ou automaticamente por condições do Home Assistant
- Os scenarios podem ser selecionados manualmente com um valor `apply_scenarios` no bloco `data` da notificação, ou automaticamente com um bloco `conditions` padrão do Home Assistant
  - As condições incluem o texto da mensagem, então uma notificação do Frigate sobre pássaros no pátio pode ser tratada de forma diferente de um intruso em uma janela
- Use scenarios para deixar as notificações menos intrusivas à noite, mais festivas nos feriados, ou para priorizar algumas mensagens
- Eles facilitam aplicar alterações em um único lugar para muitas deliveries ou notificações, e são a chave para simplificar radicalmente as chamadas de notificação nas suas automações
- Veja [Scenarios](../configuration/scenarios.md) e [Recipes](../recipes/index.md) para mais detalhes

## Prioridade (Priority) { #priority }
- Um nível de urgência para as notificações
   - Não existe uma forma padrão de priorizar notificações, dentro ou fora do Home Assistant
   - O Supernotify tem seu próprio esquema de 5 níveis, que segue as práticas mais comuns, de `minimum` a `critical`
   - A prioridade pode ser usada em regras de scenarios e deliveries, e repassada às integrações de notificação que a suportam
   - O Supernotify tem sua própria integração de e-mail, que traduz a prioridade para um formato que o Outlook, o Apple Mail etc. entendem

!!! info
    Para os mais técnicos, há um [Diagrama de classes](../developer/class_diagram.md) das classes principais correspondentes a esses conceitos.

# Princípios fundamentais { #core-principles }

1. Uma notificação só precisa de uma mensagem; todo o resto pode ter valores padrão, incluindo todos os destinos
2. O que você define em uma chamada de ação tem precedência sobre os valores padrão
   - Isso pode ser ajustado com opções como `target_usage`
   - O registro de pessoas só é usado para gerar destinos se nenhum destino for informado
3. Ação > Scenario > Delivery > Transport para configuração e valores padrão
4. O menos exigente possível quanto à forma de configurar e chamar
   - Os destinos podem ser organizados em subcategorias, ou ser uma grande lista de IDs de entidade, IDs de dispositivo, e-mails e números de telefone
   - As opções de `data` da ação, como `delivery`, podem ser um valor único, uma lista ou um dicionário

## Desenvolvedores { #developers }

Veja [Developer Concepts](../developer/concepts.md) para saber como as notificações passam por deliveries, destinos e *Envelopes*, e os [Design Principles](../developer/design/principles.md).
