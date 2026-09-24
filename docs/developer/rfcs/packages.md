# Packages

(provisional name for implementation)

## Feedback

[Github Discussion #197](https://github.com/rhizomatics/supernotify/discussions/197)

## Problem

Often SuperNotify is a small part of what's needed for example setting up notifications - Frigate involves understanding blueprints using live activities for a dishwasher requires setting up multiple automations and fine tuning mobile push the blocks. The real value from SuperNotify comes when a less technical user is able to immediately start getting notifications from things like their washing machine or dishwasher of Frigate with minimal technical understanding zero knowledge of YAML and minimal automation set up.

## Vision

When setting up Supernotify, it checks for things that could have automatic notifications configured, and asks if want to switch those on.

Each package has a detection function, which is used to discover if it can be applied, a set of default deliveries and messages (with translation keys) and the ability to customize the notification part with all the usual Supernotify options.

Everything about this is ConfigFlow based, there is no YAML required, nor offered for advanced usage.

The "packages" could also be selected after the fact, either directly in the main Supernotify ConfigFlow, or as "helper" objects.

## Implementation

A sub-package within Supernotify, with a module per package, each set up as a config subentry of the Supernotify entry. At set-up or startup the modules are called to see if they are applicable, and offer themselves through a repair issue, whose built-in *Ignore* persists the choice not to be bothered again.

Later, a thin custom component on HACS per package, purely for visibility - someone looking for help with Frigate is more likely to pick a Frigate SuperNotifier from HACS than examine Supernotify and find the small print. It would only guide the user to install Supernotify and enable the package, since HACS can't install one custom component as a dependency of another.

See [Package Support](./package_support.md) for the changes needed in Supernotify first.

### Alternatives

A separate custom component on HACS per package, holding the package logic, as Supernotify "plugins". Rejected for now, since neither HACS nor Home Assistant will install Supernotify as its dependency.

### Branding

No user facing use of term 'packages'. These will be XXXX SuperNotifier components, explained as a pre-set bundle of notifications

## Examples

### Live Notifications for Appliances

If there's a connected appliance like dishwasher, it will send a start and stop [Live Activity](https://companion.home-assistant.io/docs/notifications/live-activities) notification to mobile devices with an appropriate icon. See the very basic [recipe](../../recipes/dishwasher_live_activity.md) for current usage.

If the appliance has a time-remaining and/or progress quantity, these will be passed using the `progress` and `chronometer` values. If these are `unavailable` they're not sent and the simpler style prevails.

At the end, there's an additional notification to mobile_push only with special text "clear_notification" that will clear the live dialog box but isn't really a notification in its own right.

Where elapsed and progress are available, the notification will be periodically resent on a timer to update the bar.

If the end never happens, there's a timeout where the notification is auto-cleared.

#### Bosch / Home Connect

Example entity IDs. An actual match would be on translation keys, since users change entity IDs.

`sensor.dishwasher_operation_state` - `run`
`sensor.dishwasher_program_progress` - 84 %
`sensor.dishwasher_programme_finished` - `off`
`sensor.dishwasher_remaining_program_time` - `2026-09-16T21:44:16+00:00`
`select.dishwasher_selected_program` - `dishcare_dishwasher_program_intensiv_70`
`number.dishwasher_start_in_relative` - 0

`automation.oven_reached_temperature` - `on`
`number.oven_target_temperature` - `unavailable`
`sensor.oven_current_oven_cavity_temperature` - 59
`sensor.oven_operation_state` - `inactive`
`sensor.oven_pre_heat_finished` - `off`
`sensor.oven_program_progress` - `unavailable` %
`sensor.oven_programme_finished` - `off`
`sensor.oven_remaining_program_time` - `unavailable`

#### Power Monitored Appliances

Non-smart appliances running on a power monitor.

Potential for advanced things like learning durations and using that to estimate completion.

Also smart appliances that have gaps which a power monitor might fill, like auto power-down not being notified.

Example, from @lollox80

```
Dishwasher and washing machine are on power-monitoring smart plugs, and the dryer is SmartThings but stops reporting when off, so today each one is ~1,200 lines of YAML (power threshold + delay_on/delay_off state machine, cycle counters, maintenance reminders) plus an FSM blueprint.

Appliance package could support two detection sources from the start: native state where the integration has one (Home Connect operation_state, SmartThings *_machine_state), and a power sensor on the appliance's plug with threshold/delay options. Without remaining time, the live notification can show elapsed time via chronometer, and later estimate the end from the average of recent cycles.
```

### Motion Sensors

Home Assistant triggers have made it easier to set up automations for things like PIRs, but they still require automations with triggers and actions, and are another case where auto-detection would simplify for non-tech and expert users.

The blueprint below shows how complicated it becomes when you don't want bothered by alerts if alarm is disarmed, and you want to be very bothered if the house is unoccupied.

```yaml title="Real PIR Blueprint"
blueprint:
  name: Generic PIR alert
  description: Take action if PIR fires
  domain: automation
  input:
    motion_sensor:
      name: Motion Sensor
      description: This sensor will trigger the actions.
      selector:
        entity:
          filter:
            device_class: motion
            domain: binary_sensor

    details:
      name: Alert details
      description: Details of the sensor for alert
      default: ""
      selector:
        text:
    danger:
      name: Danger flag
      description: Is there a potential danger or just a sheep
      default: true
      selector:
        boolean:

    light:
      name: Light
      description: Light entity to switch on
      default: switch.library_standard_lamp
      selector:
        target:
          entity:
            domain: switch
    camera:
      name: CCTV Camera
      description: Camera to show on notification
      default: camera.courtyard
      selector:
        media:
    outdoors:
      name: Outdoors
      description: Is in an external zone
      default: true
      selector:
        boolean:

variables:
  motion_sensor: !input motion_sensor
  details: !input details
  danger: !input danger
  light: !input light
  camera: !input camera
  outdoors: !input outdoors
  description: "{{ details | default(state_attr(motion_sensor,'friendly_name'),true) }}"

triggers:
  - trigger: state
    entity_id: !input motion_sensor
    from: "off"
    to: "on"

action:
  - choose:
      - conditions:
          - not:
              - condition: state
                entity_id: alarm_control_panel.home_alarm_control
                state: disarmed
          - condition: time
            after: "22:00:00"
            before: "06:00:00"
          - condition: template
            value_template: "{{ danger }}"
        sequence:
          # armed, dangerous, night
          parallel:
            - action: switch.turn_on
              entity_id: switch.middle_bedroom_light
            - action: switch.turn_on
              entity_id: switch.library_standard_lamp
            - action: switch.turn_on
              continue_on_error: true
              entity_id: !input light
            - action: supernotify.notify
              continue_on_error: true
              data:
                title: "Home Security: {{ description }}"
                message: "WARNING! Night motion in {{ description }}"
                priority: high
                media:
                  camera_entity_id: !input camera

      - conditions:
          - not:
              - condition: state
                entity_id: alarm_control_panel.home_alarm_control
                state: disarmed
          - condition: time
            before: "22:00:00"
            after: "06:00:00"
          - condition: template
            value_template: "{{ danger }}"
        sequence:
          # armed, dangerous, day
          parallel:
            - action: supernotify.notify
              continue_on_error: true
              data:
                title: "Home Security: {{ description }}"
                message: "WARNING! Motion in {{ description }}"
                priority: high
                media:
                  camera_entity_id: !input camera

      - conditions:
          and:
            - condition: template
              value_template: "{{ danger and outdoors }}"
            - not:
                - condition: state
                  entity_id: alarm_control_panel.home_alarm_control
                  state: disarmed

        sequence:
          # armed, dangerous, outdoor, day or night
          - action: supernotify.notify
            continue_on_error: true
            data:
              title: "Home Security: {{ description }}"
              message: "Warning! Outdoors motion in {{ description }}"
              media:
                camera_entity_id: !input camera

      - conditions:
          and:
            - condition: template
              value_template: "{{ danger and not outdoors}}"
            - not:
                - condition: state
                  entity_id: alarm_control_panel.home_alarm_control
                  state: disarmed
            - condition: time
              after: "22:00:00"
              before: "06:00:00"

        sequence:
          # armed, dangerous, indoors, night
          parallel:
            - action: supernotify.notify
              continue_on_error: true
              data:
                title: "Home Security: {{ description }}"
                message: "WARNING! Indoors night motion in {{ description }}"
                media:
                  camera_entity_id: !input camera

      - conditions:
          condition: and
          conditions:
            - condition: or
              conditions:
                - condition: state
                  entity_id: person.joe_mctest
                  state: home
                - condition: state
                  entity_id: person.jane_mctest
                  state: home
            - condition: template
              value_template: "{{ not danger }}"
            - condition: state
              entity_id: alarm_control_panel.home_alarm_control
              state: armed_night
            - condition: time
              after: "22:00:00"
              before: "06:00:00"
        sequence:
          # armed at night, not dangerous, occupied
          parallel:
            - action: switch.turn_on
              continue_on_error: true
              entity_id: !input light
            - action: supernotify.notify
              continue_on_error: true
              data:
                title: "Home Security: {{ description}}"
                message: "Night motion while occupied in {{ description }}"
                priority: low
                media:
                  camera_entity_id: !input camera
```

### Frigate

The [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints/tree/main/Frigate_Camera_Notifications) works well, however using Blueprints is still not very non-tech friendly, a lot of the blueprint logic is doing things in clumsy YAML that are already done in Supernotify, and there are some long standing bugs like mobile groups to work around.

The Frigate `package` would pick up that there's a known MQTT topic or Frigate proxy, and set up an MQTT subscription for mobile push, email and voice announce by default. It would offer everything the blueprint has, address known bugs and workarounds like faking a `notify_device` and avoiding broken images.

See [Frigate SuperNotifier](./frigate_supernotifier.md) for the design.


```yaml title="Current Supernotify usage of Frigate Blueprint"
use_blueprint:
    path: frigate/beta.yaml
    input:
      camera:
      - camera.driveway_frigate
      notify_device: ad4dccb09ec6fd181fb01aecb8de3785
      notify_group: supernotifier
      critical: true
      labels:
      - car
      - bicycle
      - motorcycle
      video: '{{base_url}}/api/frigate{{client_id}}/notifications/{{id}}/{{camera}}/master.m3u8'
      presence_filter:
      - ''
      mqtt_topic: frigate/reviews
      ios_live_view: camera.driveway
      base_url: https://home.23acaciaavenue.org
      tap_action: '{{base_url}}/api/frigate{{client_id}}/notifications/{{id}}/{{camera}}/master.m3u8'
```

Frigate could have multiple flows - regular event detection (`frigate/reviews`), GenAI events (`frigate/tracked_object_update`) with different options per camera, or using message checks or HA state to prioritize or tune delivery.

```yaml title="Real Frigate Scenarios"
  silence_frigate:
    alias: No notification for uninteresting frigate genai
    conditions:
      condition: and
      conditions:
        - "{{'A Person, Billy' in notification_message|upper}}"
        - "{{'A Person, Jean' in notification_message|upper}}"
        - "{{'UNKNOWN BIRD' in notification_message|upper}}"
        - condition: state
          entity_id: alarm_control_panel.home_alarm_control
          state:
            - disarmed
            - armed_home
            - armed_night
    delivery:
      .*:
        enabled: false
  person_detected_disarmed:
    alias: only chime for people when disarmed
    delivery:
      .*:
        enabled: false
    conditions:
      condition: and
      conditions:
        - "{{'person was detected' in notification_message|lower }}"
        - condition: state
          entity_id: alarm_control_panel.home_alarm_control
          state:
            - disarmed
```

Live Activities would be a great fit for ongoing events in Frigate, where its possible to tie together what's happening. Though to be really useful this could be a mixture of PIRs, Frigate Events, Driveway Alarms etc and probably require some sort of AI to make sensible guess when an event ("the postman visits") starts and ends.

## Questions

- What does the UI look like? Does this fit into an existing HA concept?
- Should it generate actual notifications or be entirely in code?
  - Preference for code, since that means future releases can easily make deliver improvements for existing users
  - Possibility for an `export` function, but advanced. Audience would be people who want their own automations, but need to get started, though that's an LLM use case nowadays
- Are those multiple Frigate cameras, and priorities, and GenAI detections multiple packages? sub-packages?
  - Is there a package per camera, and a separate one for the GenAI events?
- "Packages" isn't a great name, but can't be anything that clashes with Home Assistant nomenclature
  - "Notification Presets"?
  - "Routines"?
  - Reuse "Recipe" - manual recipes in the docs, automatic recipes in the code. Though recipe sounds like a set of steps for doing things yourself, this is more like buying the cake already baked and iced.
