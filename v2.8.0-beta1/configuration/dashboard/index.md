# Dashboard

Create a dashboard to use, configure and debug notifications using [Supernotify Cards](https://github.com/lollox80/supernotify-cards/blob/main/README.md).

Use the instructions at [Adding YAML Dashboards](https://www.home-assistant.io/dashboards/dashboards/#adding-yaml-dashboards) to add to your own home instance.

Easiest way is to add an empty dashboard, choose **Edit Dashboard → Raw Configuration Editor** from the pencil icon at top-right, and paste in the YAML below. Once that's done, the dashboard can be edited visually and never have to see YAML again.

## Configuration

Example Dashboard

```yaml
views:
  - type: sections
    max_columns: 4
    title: Overview
    path: overview
    sections:
      - type: grid
        cards:
          - type: heading
            heading_style: title
          - type: custom:supernotify-control-card
            dnd_entity: input_boolean.notifier_dnd
            snooze_minutes: 30
            tiles:
              - dnd
              - snooze
              - announce
            groups: []
          - type: custom:supernotify-stats-card
            days: 14
      - type: grid
        cards:
          - type: heading
            heading_style: title
          - type: custom:supernotify-overview-card
            poll_seconds: 60
    icon: mdi:view-dashboard-variant
    cards: []
    show_icon_and_title: true
  - type: sections
    sections:
      - type: grid
        cards:
          - type: heading
            heading: Send a Notification
            heading_style: title
            icon: mdi:message-text-fast-outline
          - type: custom:supernotify-composer-card
    header:
      card:
        type: markdown
        text_only: true
        content: '# Supernotify'
    max_columns: 4
    title: Send
    cards: []
    icon: mdi:email-fast
    show_icon_and_title: true
  - type: sections
    max_columns: 4
    title: People and Scenarios
    path: people-and-scenarios
    icon: mdi:account-multiple
    sections:
      - type: grid
        cards:
          - type: custom:supernotify-scenarios-card
      - type: grid
        cards:
          - type: heading
            heading_style: title
            icon: ''
          - type: custom:supernotify-recipients-card
          - type: custom:supernotify-bands-card
            bands:
              early_morning:
                start: input_datetime.notifier_start_early_morning
                volume: input_number.notifier_early_morning_volume
              morning:
                start: input_datetime.notifier_start_morning
                volume: input_number.notifier_morning_volume
              afternoon:
                start: input_datetime.notifier_start_afternoon
                volume: input_number.notifier_afternoon_volume
              evening:
                start: input_datetime.notifier_start_evening
                volume: input_number.notifier_evening_volume
              night:
                start: input_datetime.notifier_start_night
                volume: input_number.notifier_night_volume
              late_night:
                start: input_datetime.notifier_start_late_night
                volume: input_number.notifier_late_night_volume
    show_icon_and_title: true
    cards: []
  - type: masonry
    path: configuration
    title: Delivery Channels
    cards:
      - type: custom:supernotify-transports-card
      - type: custom:supernotify-deliveries-card
        hide_defaults: true
    icon: mdi:truck-delivery
    show_icon_and_title: true
  - type: masonry
    path: debug
    title: Debug
    cards:
      - type: markdown
        content: >-
          ![Supernotify
          Logo](https://supernotify.rhizomatics.org.uk/dev/assets/images/dark_icon.png)

          - [Supernotify
          Documentation](https://supernotify.rhizomatics.org.uk/latest/)

          - [What's
          New](https://supernotify.rhizomatics.org.uk/latest/changelog/)

          - [Supernotify
          Cards](https://github.com/lollox80/supernotify-cards/blob/main/README.md)

          - [Recipes](https://supernotify.rhizomatics.org.uk/latest/recipes/)
      - type: tile
        entity: update.supernotify_update
        features:
          - type: update-actions
      - type: custom:supernotify-automations-card
      - type: custom:supernotify-simulator-card
      - type: vertical-stack
        cards:
          - type: markdown
            content: >-
              Requires a sensor to be set up first to index the archived
              notifications, see [Supernotify Archive
              Card](https://github.com/lollox80/supernotify-cards/blob/main/README.md#supernotify-archive-card)
          - type: custom:supernotify-archive-card
            entity: sensor.supernotify_archivio
    icon: mdi:cog-stop-outline
    show_icon_and_title: true
```
