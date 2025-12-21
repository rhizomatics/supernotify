---
tags:
  - frigate
  - recipe
  - cctv
  - genai
  - gemini
  - alexa
  - echo
  - accessibility
  - template
  - condition
title: Recipe for Voice Described CCTV with GenAI
description: Use a combination of Home Assistant, Supernotify, Frigate, Alexa Devices integration and Google Gemini to announcement events around the property
---
# Recipe - Voice Described CCTV with GenAI

## Purpose

A voice assistant will announce a description of events discovered on CCTV camera, with an evaluation of risk.

## Implementation

This is an advanced recipe, requiring several moving parts in addition to Supernotify, although it will
also work with any notify implementation. It uses both AI image detection to work out when something interesting happened on camera, and GenAI ( an 'LLM' ) to interpret what is happening in the scene, and what the potential risk level is, for example if a suspicious intruder is present.

* Frigate CCTV
    * For *Mobile Push* and/or *Email* transports, use [Frigate Proxy]() for Home assistant if Frigate is not running as a Home Assistant app (aka 'add-on') to support a click-thru link to the camera page
* GenAI API subscription compatible with Frigate
    * In this example, the **Google Gemini** free tier is used
    * Follow the instructions for Frigate (see [references](#references-and-further-reading)) to generate an *API Key* and add it to the Frigate configuration
* MQTT Broker configured in Home Assistant
* Home Asssistant template logic
* Voice Assistant
    * In this example, Amazon Echo devices using the *Alexa Devices* integration, although *Alexa Media Player* can be easily switched for it
    * If you don't have one of these, then use another voice assistant, Mobile Push, e-mail or similar


## Example Configuration

### Frigate

This assumes you already have your cameras set up in Frigate, and an `mqtt` section pointing to the
same broker as used by Home Assistant.

Tune the context to describe your house, location, car and occupants.

```yaml
genai:
  enabled: true
  provider: gemini
  api_key: <insert your key here>
  model: gemini-flash-lite-latest
  prompt: Analyze the {label} in these images from the {camera} security camera.
    Focus on the actions, behavior, and potential intent of the {label}, rather
    than just describing its appearance. The cameras are located on an detached
    house in a quarter acre plot, facing south west in a suburban street in
    London, England. There is a neighbourhood watch scheme, and a couple of
    burglaries at night in the past 5 years.
    A family lives here, a 6 foot tall man in 30s with short brown hair who works
    from home, a 5 foot 5 inch woman who commutes to work and a teenaged son who
    walks to a nearby school. They drive a blue Subaru Forester, registration
    PK19KHG which is parked in a driveway in the back garden.
    There are two cameras, a Dahua PTZ mounted under the eaves on first floor pointing
    at the back garden, and a doorbell camera on the front door.
    Produce a concise summary, dont include any preamble, start immediately with the
    risk level as a single upper case word, one of "NO RISK","LOW RISK",
    "MEDIUM RISK","HIGH RISK" or "CRITICAL RISK". Follow that with a short of summary
    of what the object is, then what it is doing and finally any rationale for
    why the risk level has been determined. The results will appear on an Apple
    push notification on iPhone which only shows the first 178 characters. No extra
    line feeds in the message. Do not describe the vegetation or other static
    details. For vehicles, focus on the movement, direction or purpose, such as
    parking, approaching, circling. If it is a delivery vehicle, mention the
    company. For people, summarize what they are doing and what their actions
    suggest about their intent, for example approaching a door, standing still,
    appearing to not know their surroundings.
```

### Home Assistant

This assumes that you have `delivery` configurations for `alexa_announce` and `mobile_push` and
that you have Home Assistant available at `http://homeassistant.local:8123`.

The automation subscribes to the Frigate MQTT topic, ignores certain messages, strips the "MEDIUM RISK" etc
preface off the message and derives the notification priority from the risk level assessed by GenAI.

The [mobile push transport adaptor](../transports/mobile_push.md) will automatically, for iOS, set the `interruption-level` set to `time-sensitive` for `high` priority notifications, and a `critical` for critical ones. The latter will also have the `critical` sound played at full volume.

```yaml
automations:
- id: '1748700232868'
  alias: Frigate gemini updates
  description: 'Textual descriptions of Frigate events for mobile push and Alexa'
  triggers:
  - trigger: mqtt
    topic: frigate/tracked_object_update
    value_template: '{{ value_json.type }}'
    payload: description
  conditions:
  - condition: template
    value_template: '{{trigger.payload_json is defined and not trigger.payload_json.description.startswith(''NO RISK'')
      and not trigger.payload_json.description.startswith(''LOW RISK'') and not trigger.payload_json.description.startswith(''UNKNOWN'')'
  actions:
  - action: notify.supernotify
    data:
      message: >-
          {% set description = trigger.payload_json.description %}
          {{ description | regex_replace('^(\w+)\s+RISK\s+','',ignorecase=True) | lower}}
      title: Update on activity at {{trigger.payload_json.camera}}
      data:
        priority: >-
            {% set regex = "(\w+)\s+RISK\s+.*" %}
            {% set description = trigger.payload_json.description %}
            {% if description is match(regex,ignorecase=True) %}
            {{ description | regex_findall_index(regex,ignorecase=True) | lower}}
            {% else %}
            medium
            {% endif %}
        media:
          snapshot_url: http://homeassistant.local:8123/api/frigate/notifications/{{trigger.payload_json.id}}/thumbnail.jpg
          camera_entity_id: camera.{{trigger.payload_json.camera}}
        delivery:
          - alexa_announce
          - mobile_push
```

## Variations

* Use a *scenario* in Supernotify to handle messages differently by risk
   * For example dropping the "NO RISK" ones and sending the "CRITICAL RISK" ones out by email and time-sensitive mobile push (
   * The [Mobile Push Transport Adaptor](../transports/mobile_push.md) will automatically set the iOS critical or high priority configuration based on message priority)
   * See the [Content Escalation Recipe](content_escalation.md) for an example of
   doing this with basic Frigate occupancy events
* Move a PTZ camera to point at the location mentioned in the GenAI generated notification
   * The [Move a Camera for Snapshot](./move_a_camera_for_snapshot.md) recipe will show you how
* Tune the context in Frigate to make it more relevant for the notifications
   * Gemini will pick up on things like typical behaviours of the occupants, local crime history, regular visitors

### Overriding priority from GenAI assessed risk

If the GenAI has been asked to set the risk at the beginning of the message, like the example above,
then you can use a *Scenario* to reflect this in the message priority ( to the extent you trust it, you
might want to keep `critical` for things that don't hallucinate quite as often, like smoke alarms).

These two scenarios will not only override the email priority, but also trim off the risk statement since the
message is already at the right priority. That's completely optional, and remove the `message_template` if
you like the whole message.

```yaml title="Supernotify config snippet"
  high_risk:
      conditions: "{{notification_message is match('HIGH RISK',ignorecase=True) }}"
      delivery:
        plain_email:
          data:
            priority: high
            message_template: "{{notification_message | regex_replace('high risk[:!]*','',ignorecase=True) | trim}}"

    low_risk:
        conditions: "{{notification_message is match('LOW RISK',ignorecase=True)}}"
        delivery:
          plain_email:
            data:
              priority: low
              message_template: "{{notification_message | regex_replace('low risk[:!]*','',ignorecase=True) | trim}}"

```

Note that you have to set priority and message per delivery - a future Supernotify might make this easier to do in bulk.

### Tuning GenAI for Specific Objects

In this case, improve the analysis of birds detected by Frigate

```yaml title="Frigate config snippet"
genai:
  object_prompts:
      bird: Analyze the bird in the image and attempt to determine the species,
        which might be provided by Frigate as {sub_label}. Start the summary
        with either BIRD IDENTIFIED in capitals or UNKNOWN BIRD.
        Common species at the location include pheasants, crows, wrens,
        nuthatches, tits, blackbirds, goldfinches, cuckoos, owls, chaffinches,
        buzzards, robins and herons. Do not explain the reasoning, say only the
        species of bird, and where it is. If it is not a direct match, prefix
        the species with 'probably', if no match can be determined, say 'unknown
        species'. Give the location with reference to the {camera} camera and where on
        the property
```

### Adjusting Notifications For Content

This scenario will downgrade messages when a bird is seen so that there's only a mobile push, and
no e-mail, Alexa announcement or other regular ways of notifying.

```yaml title="Supernotify config snippet"
scenarios:
    known-birds:
      alias: Don't email or announce about birds
      conditions:
        condition: and
        conditions:
          - "{{notification_priority in ['low','medium']}}"
          - condition: or
            conditions:
              - "{{'BIRD IDENTIFIED' in notification_message|upper}}"
              - "{{'UNKNOWN BIRD' in notification_message|upper}}"
      delivery:
        - apple_push
    unknown_birds:
      alias: Don't send out any notifications if the bird can't be identified
      conditions: "{{'UNKNOWN BIRD' in notification_message|upper}}"
      delivery:
        apple_push:
          enabled: false
        plain_email:
          enabled: false
```

## References and Further Reading

* Frigate
    * [Generative AI](https://docs.frigate.video/configuration/genai/)
    * [Home Assistant Integration](https://docs.frigate.video/integrations/home-assistant/)
    * [Home Assistant Notifications](https://docs.frigate.video/guides/ha_notifications)
    * [Proxy for Home Assistant](https://github.com/blakeblackshear/frigate-hass-addons/tree/main/frigate_proxy)
* [Google Gemini Free Tier](https://ai.google.dev/gemini-api/docs/pricing)
* [Home Assistant Templating](https://www.home-assistant.io/docs/configuration/templating)
