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
     <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Ajouter à HACS">
   </a>
<br/>
<br/>
<br/>

**Notifications Unifiées pour Home Assistant**

Une **interface de notification unifiée** par-dessus la plateforme `notify` intégrée de Home Assistant, pour simplifier considérablement les canaux de notification multiples et les scénarios complexes, notamment les notifications multicanaux, les notifications conditionnelles, les actions mobiles, les captures d'écran de caméras, les carillons et les e-mails HTML basés sur des modèles.

Supernotify a un seul objectif : **permettre à la notification la plus simple possible d'envoyer autant de notifications que nécessaire, sans code et avec une configuration minimale**.

Cela permet de garder les automatisations, scripts et applications AppDaemon simples et faciles à maintenir, avec tous les détails et règles gérés en un seul endroit. La notification la plus petite possible — uniquement un message — peut suffire à tout déclencher. Modifiez les adresses e-mail en un seul endroit et laissez Supernotify déterminer quelles applications mobiles utiliser.

Avec seulement deux lignes de YAML très simple, commencez à envoyer des notifications push mobiles à tous les membres de la maison, sans configurer les noms des applications mobiles dans les notifications.


## Distribution

Supernotify est un composant personnalisé disponible via le [Home Assistant Community Shop](https://hacs.xyz) (**HACS**). Il est gratuit et open source sous la [licence Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0).

## Documentation

Essayez [Démarrage](https://supernotify.rhizomatics.org.uk/getting_started/), l'explication des [concepts fondamentaux](https://supernotify.rhizomatics.org.uk/concepts/) et les [adaptateurs de transport](https://supernotify.rhizomatics.org.uk/transports/) disponibles. [Notification](https://supernotify.rhizomatics.org.uk/usage/notifying/) montre comment appeler Supernotify depuis des automatisations ou la page des outils de développement.

Il y a beaucoup de [recettes](https://supernotify.rhizomatics.org.uk/recipes/) avec des exemples de configuration, ou parcourez par [tags](https://supernotify.rhizomatics.org.uk/tags/).


## Fonctionnalités

* Une action -> Plusieurs notifications
    * Supprimez la configuration et le code répétitifs des automatisations
    * Les adaptateurs ajustent automatiquement les données de notification pour chaque intégration
    * Par exemple, utilisez avec un [Blueprint Frigate](https://github.com/SgtBatten/HA_blueprints) pour recevoir des captures de caméras par e-mail
* Configuration automatique
    * Configuration de livraison pour les notifications push mobiles, e-mail (SMTP) et entités de notification configurées automatiquement
    * Applications mobiles découvertes automatiquement, incluant le fabricant et le modèle du téléphone
    * Appareils Alexa pour les carillons découverts automatiquement
* Au-delà des intégrations `notify`
    * Carillons, sirènes, SMS, TTS, annonces et sons Alexa, appels API, appareils MQTT,  Gotify, ntfy
    * Toutes les implémentations standard `notify` et `notify.group` disponibles
    * Utilisation grandement simplifiée des notifications push mobiles, par ex. pour iPhone
* Notifications conditionnelles
    * Utilisant les `conditions` standard de Home Assistant
    * Variables de condition supplémentaires ajoutées, incluant le message et la priorité
    * Combinez avec la détection d'occupation pour personnaliser les notifications
* **Scénarios** pour une configuration simple et concise
    * Regroupez des blocs de configuration et de logique conditionnelle communs
    * Appliquez à la demande (`red_alert`, `nerdy`) ou automatiquement selon des conditions
* Modèle de personne unifié
    * Définissez un e-mail, un numéro SMS ou un appareil mobile, puis utilisez l'entité `person` dans les actions de notification
    * Les personnes sont auto-configurées avec leurs applications mobiles
* **Modèles d'e-mail HTML** faciles
    * Jinja2 standard de Home Assistant, défini dans la configuration YAML, les appels d'action ou des fichiers autonomes
    * Modèle général par défaut fourni
* **Actions mobiles**
    * Configurez un ensemble cohérent d'actions mobiles pour plusieurs notifications
    * Incluez des actions de *snooze* pour mettre en sourdine selon des critères
* **Captures d'images** flexibles
    * Prend en charge les caméras, les images MQTT et les URL d'images
    * Repositionnez les caméras vers des préréglages PTZ avant et après une capture
* Choix du niveau de configuration
    * Définissez des valeurs par défaut au niveau du transport, de la livraison et de l'action
* Suppression des **notifications en double**
    * Paramétrez le délai avant de réautoriser
* **Archivage** et **support de débogage** des notifications
    * Archivez optionnellement les notifications vers le système de fichiers et/ou un topic MQTT
    * Inclut des informations de débogage complètes
    * Livraisons, transports, destinataires et scénarios exposés comme entités dans l'interface Home Assistant


## Du YAML nécessaire

Supernotify prend actuellement en charge uniquement la [configuration basée sur YAML](https://supernotify.rhizomatics.org.uk/configuration/yaml/). Avec seulement 2 lignes de configuration copier-coller, vous pouvez déjà faire beaucoup :

```yaml title="Avec les 2 lignes YAML par défaut"
  - action: notify.supernotify
    data:
        message: Bonjour ! Test de Supernotify envoyant vers les applications mobiles de tout le monde
```


##  Rhizomatics Open Source pour Home Assistant

### HACS
- [AutoArm](https://autoarm.rhizomatics.org.uk) - Armer et désarmer automatiquement les panneaux de contrôle d'alarme Home Assistant avec des boutons physiques, la présence, les calendriers et plus
- [Remote Logger](https://remote-logger.rhizomatics.org.uk) - Capture d'événements OpenTelemetry (OTLP) et Syslog pour Home Assistant


### Python / Docker

- [Anpr2MQTT](https://anpr2mqtt.rhizomatics.org.uk) - Intégration avec les caméras ANPR/ALPR via le système de fichiers vers MQTT
- [Updates2MQTT](https://updates2mqtt.rhizomatics.org.uk) - Notification automatique via MQTT lors des mises à jour d'images Docker

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Default-blue.svg
