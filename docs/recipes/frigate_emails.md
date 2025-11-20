---
tags:
  - frigate
  - recipe
  - email
  - cctv
---
# Recipe - Frigate Emails

## Purpose

The [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints/blob/main/Frigate_Camera_Notifications) is used to create mobile push notifications, with the image embedded
and links to the Frigate UI. You need to have this also as email for family members without
mobile push available.

## Implementation

Specify your Supernotify platform as the `notify_group`, and within Supernotify make sure email is configured. The mobile push config will automatically be turned into attachments and text for the email.

Note that `notify_device` currently needs specified to suppress Frigate template errors, any old ID will do.

## Example Configuration

```yaml
automations:
- id: frigate-driveway-apple-critical-event
  alias: Generate critical apple event for frigate driveway
  description: Driveway CCTV Mobile Notification
  use_blueprint:
    path: frigate/beta.yaml
    input:
      camera:
        - camera.driveway
      notify_device: 2a8802529e7609d06c47e1334c2facf7
      notify_group: supernotifier
      critical: true
```

## Variations

- Use this anywhere else you want to get multiple notification channels without changing templates
- Simplify automations and templates by moving complex setup and rules into Supernotify, such as using a single **Scenario** to configure dozens of automations
- Have Alexa devices announce the notification too, using the `alexa_devices` or `alexa_media_player` integrations, or have a sound alert via an Alexa or 433Mhz doorbell chime
