# Recipe - Voice Described CCTV

## Purpose

A voice assistant will announce a description of events discovered on CCTV camera, with an evaluation of risk.

## Implementation

This is an advanced recipe, requiring several moving parts in addition to Supernotify. It uses both AI image
detection to work 

* Frigate CCTV
    * For *Mobile Push* and/or *Email* transports, use  *Frigate Proxy* for Home assistant if Frigate is not running as a Home Assistant app (aka 'add-on') to support a click-thru link to the camera page
* GenAI API subscription compatible with Frigate
    * In this example, the Google Gemini free tier is used
    * Follow the instructions for Frigate (see [references](#references-and-further-reading)) to generate an *API Key* and add it to the Frigate configuration
* MQTT Broker configured in Home Assistant
* Home Asssistant template logic
* Voice Assistant
    * In this example, Amazon Echo devices using the *Alexa Devices* integration, althought *Alexa Media Player* can be easily switched for it
    * If you don't have one of these, then use Mobile Push, e-mail or similar


## Example Configuration

### Frigate

This assumes you already have your cameras set up in Frigate, and an `mqtt` section pointing to the
same broker as used by Home Assistant.
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

* Use a *scenario* in Supernotify to handle messages differently by risk, for example dropping the "NO RISK" ones
and sending the "CRITICAL RISK" ones out by email and time-sensitive mobile push ( the [Mobile Push Transport Adaptor](../transports/mobile_push.md) will automatically set the iOS critical or high priority configuration based on message priority)
* Move a PTZ camera to point at the location mentioned in the GenAI generated notification, see [Move a Camera for Snapshot](./move_a_camera_for_snapshot.md) recipe
* Tune the context in Frigate to make it more relevant for the notifications, Gemini will pick up on things like
typical behaviours of the occupants, or local crime history

## References and Further Reading

* Frigate
    * [Generative AI](https://docs.frigate.video/configuration/genai/)
    * [Home Assistant Integration](https://docs.frigate.video/integrations/home-assistant/)
    * [Proxy for Home Assistant](https://github.com/blakeblackshear/frigate-hass-addons/tree/main/frigate_proxy)
* [Google Gemini Free Tier](https://ai.google.dev/gemini-api/docs/pricing)
* [Home Assistant Templating](https://www.home-assistant.io/docs/configuration/templating)
