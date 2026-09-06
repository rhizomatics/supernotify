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
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Adicionar ao HACS">
   </a>
<br/>
<br/>
<br/>

**Notificações Unificadas para Home Assistant**

### ALTERAÇÃO IMPORTANTE v2.0.0

>> A versão `2.0.0` do SuperNotify passa a usar uma configuração nativa da interface do Home Assistant ('ConfigFlow'). Se já tiver uma configuração simples, tudo será migrado automaticamente por si e não será necessário YAML.

>> Se tiver uma configuração avançada (entregas, cenários, câmeras, pessoas, ações etc.), será gerada uma *reparação* para mover essas definições para um novo ficheiro `supernotify.yaml` e adicionar uma instrução `include` ao seu `configuration.yaml`. Ou pode optar por mover a configuração manualmente para fora do bloco `notify`, da forma que preferir.

>> Em qualquer dos casos, nada será eliminado ou comentado, pelo que será fácil reverter a alteração. Remova a configuração antiga quando tiver a certeza de que a nova versão está a funcionar bem para si. Isto também removerá o aviso `[homeassistant.components.notify] Failed to initialize notification service supernotify` do registo, que provém da implementação antiga do notify.

Uma **interface de notificação unificada** sobre a plataforma `notify` integrada do Home Assistant, para simplificar consideravelmente múltiplos canais de notificação e cenários complexos, incluindo notificações multicanal, notificações condicionais, ações móveis, capturas de câmera, carrilhões e e-mails HTML baseados em modelos.

Supernotify tem um único objetivo — **fazer com que a notificação mais simples possível envie tantas notificações quanto necessário, sem código e com configuração mínima**.

Isso mantém as automações, scripts e aplicativos AppDaemon simples e fáceis de manter, com todos os detalhes e regras gerenciados em um único lugar. A menor notificação possível — apenas uma mensagem — pode ser suficiente para acionar tudo. Altere endereços de e-mail em um único lugar e deixe o Supernotify determinar quais aplicativos móveis usar.

Apenas com a configuração da interface, comece as notificações push móveis para todos os registrados em casa, sem configurar os nomes dos aplicativos móveis nas notificações.

![Exemplo de ação de notificação](../assets/images/notification.png){width=500}

## Distribuição

Supernotify é um componente personalizado disponível através do [Home Assistant Community Shop](https://hacs.xyz) (**HACS**). É gratuito e de código aberto sob a [licença Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0).

## Documentação

Experimente o [Início Rápido](https://supernotify.rhizomatics.org.uk/getting_started/), a explicação dos [conceitos fundamentais](https://supernotify.rhizomatics.org.uk/concepts/) e os [adaptadores de transporte](https://supernotify.rhizomatics.org.uk/transports/) disponíveis. [Notificando](https://supernotify.rhizomatics.org.uk/usage/notifying/) mostra como chamar o Supernotify a partir de automações ou da página de ferramentas do desenvolvedor.

Há muitas [receitas](https://supernotify.rhizomatics.org.uk/recipes/) com exemplos de configuração, ou navegue por [tags](https://supernotify.rhizomatics.org.uk/tags/).


## Funcionalidades

* Uma ação -> Múltiplas notificações
    * Remova configurações e código repetitivos das automações
    * Os adaptadores ajustam automaticamente os dados de notificação para cada integração
    * Por exemplo, use com um [Blueprint do Frigate](https://github.com/SgtBatten/HA_blueprints) para receber capturas de câmera por e-mail
* Configuração automática
    * Configuração de entrega para notificações push móveis, e-mail (SMTP) e entidades de notificação configurada automaticamente
    * Aplicativos móveis descobertos automaticamente, incluindo fabricante e modelo do telefone
    * Dispositivos Alexa para carrilhões descobertos automaticamente
* Além das integrações `notify`
    * Carrilhões, sirenes, SMS, TTS, anúncios e sons Alexa, chamadas de API, dispositivos MQTT, Gotify, ntfy
    * Todas as implementações padrão `notify` e `notify.group` disponíveis
    * Uso muito simplificado de notificações push móveis, por ex. para iPhone
* Notificações condicionais
    * Usando `conditions` padrão do Home Assistant
    * Variáveis de condição adicionais, incluindo mensagem e prioridade
    * Combine com detecção de ocupação para personalizar notificações
* **Cenários** para configuração simples e concisa
    * Agrupe blocos comuns de configuração e lógica condicional
    * Aplique sob demanda (`red_alert`, `nerdy`) ou automaticamente com base em condições
* Modelo unificado de pessoa
    * Defina um e-mail, número de SMS ou dispositivo móvel e use a entidade `person` em ações de notificação
    * Pessoas são configuradas automaticamente junto com seus aplicativos móveis
* **Modelos de e-mail HTML** fáceis
    * Jinja2 padrão do Home Assistant, definido na configuração YAML, em chamadas de ação ou como arquivos independentes
    * Modelo geral padrão incluído
* **Ações móveis**
    * Configure um conjunto consistente de ações móveis para múltiplas notificações
    * Inclua ações de *soneca* para silenciar com base em critérios
* **Capturas de imagem** flexíveis
    * Suporta câmeras, imagens MQTT e URLs de imagens
    * Reposicione câmeras para predefinições PTZ antes e depois de uma captura
* Escolha do nível de configuração
    * Defina padrões no nível do adaptador de transporte, entrega e ação
* Supressão de **notificações duplicadas**
    * Configure o tempo de espera antes de reautorizar
* **Arquivamento** de notificações e **suporte a depuração**
    * Arquive opcionalmente notificações no sistema de arquivos e/ou tópico MQTT
    * Inclui informações completas de depuração
    * Entregas, transportes, destinatários e cenários expostos como entidades na interface do Home Assistant


## YAML apenas para uso avançado

Atualmente, o Supernotify suporta a configuração padrão pela interface do Home Assistant para a configuração básica, e [configuração YAML](https://supernotify.rhizomatics.org.uk/configuration/yaml/) para recursos avançados. O YAML será mantido para facilitar o trabalho com bases de regras maiores.

Muito pode ser feito com a simples configuração sem YAML, incluindo a automação da configuração de push móvel. Veja as [receitas](recipes/index.md) na documentação, e este exemplo de push móvel:

```yaml title="Com zero YAML, tudo configurado pela interface"
  - action: supernotify.notify
    data:
        message: Olá! Testando o Supernotify enviando para os aplicativos móveis de todos
```


##  Rhizomatics Open Source para Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Armar e desarmar automaticamente painéis de controle de alarme do Home Assistant usando botões físicos, presença, calendários e mais
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - Captura de eventos OpenTelemetry (OTLP) e Syslog para Home Assistant


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Integração com câmeras ANPR/ALPR de placas via sistema de arquivos para MQTT
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Notificação automática via MQTT em atualizações de imagens Docker

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
