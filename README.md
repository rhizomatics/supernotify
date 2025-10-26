[![Rhizomatics Open Source](https://avatars.githubusercontent.com/u/162821163?s=96&v=4)](https://github.com/rhizomatics)

# Supernotify

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/rhizomatics/supernotify)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/rhizomatics/supernotify/main.svg)](https://results.pre-commit.ci/latest/github/rhizomatics/supernotify/main)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/:user/:repo/:workflow)
[![CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/github-code-scanning/codeql)
[![Dependabot Updates](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/rhizomatics/supernotify/actions/workflows/dependabot/dependabot-updates)


Easy multi-channel rich notifications.

An extension of HomeAssistant's built in `notify.notify` that can greatly simplify multiple notification channels and
complex scenarios, including multi-channel notifications, conditional notifications, mobile actions, chimes and template based HTML emails. Can substitute directly for existing notifications to mobile push, email, etc.

## Features

* Send out notifications on multiple channels from one call, removing repetitive config and code from automations
* Standard `notify` implementation so easy to switch out for other notify implementations, or `notify.group`
* Conditional notification using standard Home Assistant `condition` config
* Reuse chunks of conditional logic as *scenarios* across multiple notifications
* Streamlined conditionals for selecting channels per priority and scenario, or
for sending only to people in or out of the property
* Use `person` for all notification configuration, regardless of channel
  * Unified Person model currently missing from Home Assistant
* HTML email templates, using Jinja2, with a general default template supplied
* Single set up of consistent mobile actions across multiple notifications
* Flexible image snapshots, supporting cameras, MQTT Images and image URLs.
  * Cameras can be repositioned using PTZ before and after a snapshot is taken.
* Defaulting of targets and data in static config, and overridable at notification time
* Generic support for any notification method
  * Plus canned delivery methods to simplify common cases, especially for tricky ones like Apple Push
* Reloadable configuration
* Tunable duplicate notification detection
* Well-behaved `notify` extension, so can use data templating, `notify.group` and other notify features.
* Refactor out repetitive configuration for ease of maintenance
* Debugging support,
  * Optional archival of message structures
  * Additional actions ( previously known as services ) to pull back live configuration or last known notification details.

## Installation

* Add git repo to HACS as custom repo
* Select *SuperNotify* in the list of available integrations in HACS and install
* Add a `notify` config for the `supernotify` integration, see `examples` folder
* In order to use email attachments, e.g. from camera snapshot or a `snapshot_url`,
you must set the `allowlist_external_dirs` in main HomeAssistant config to the same as
`media_path` in the supernotify configuration


## Usage

### Minimal
```yaml
  - action: notify.supernotifier
    data:
        title: Security Notification
        message: '{{state_attr(sensor,"friendly_name")}} triggered'
```

### More features
```yaml
  - action: notify.supernotifier
    data:
        title: Security Notification
        message: '{{state_attr(sensor,"friendly_name")}} triggered'
        target:
          - person.jim_bob
          - person.neighbour
        priority: high
        apply_scenarios:
          - home_security
          - garden
        constrain_scenarios:
        delivery:
            mobile_push:
                data:
                    clickAction: https://my.home.net/dashboard

```
Note here that the `clickAction` is defined only on the `mobile_push` delivery. However
its also possible to define everything at the top level `data` section and let the individual
deliveries pick out the attributes they need. This is helpful either if you don't care about
fine tuning delivery configurations, or using existing notification blueprints, such as the popular
[Frigate Camera Notification Blueprints](https://github.com/SgtBatten/HA_blueprints/tree/main/Frigate%20Camera%20Notifications).


### Templated
```yaml
  - action: notify.supernotifier
    data:
        message:
    data_template:
        title: Tank Notification
        message:  "Fuel tank depth is {{ state_attr('sensor.tank', 'depth') }}"
        data:
            priority: {% if {{ state_attr('sensor.tank', 'depth') }}<10 }critical{% else %}medium {% endif %}
```

 See the [Recipes](recipes/index.md) for more ideas.

## Delivery Methods

### Mobile Push

Send a push message out, with option for camera integration, mobile actions, and
translate general priority to Apple specific push priority.

Some functionality may also work with Android push, though has not been tested.

Although Supernotify will automatically set most useful mobile push options,
its also possible to directly set them, as in this example:

```yaml
  - action: notify.supernotifier
    data:
      message: Movement at garden gate
      data:
        priority: high
        media:
          camera_entity_id: camera.porch
          camera_ptz_preset: garden_gate
        action_groups:
          - security_actions
        delivery:
          mobile_push:
            data:
              tag: "backyard-motion-detected"
              presentation_options:
                - alert
                - badge
              push:
                sound:
                  name: "US-EN-Alexa-Motion-Detected-Generic.wav"
                  volume: 1.0
```

### Chime

Notify using a sound of your choosing - for example a doorbell, barking dog, siren or recording.
This works with a variety of devices, from cheap 433Mhz doorbell units to Amazon Echo devices.

You can mix and match any of these devices, and also map their different implementations to the
same logical sound using simple alias names, for example `doorbell`. Then within notifications, you
can ask for a doorbell sound and it will generated by each device in its own way. Even if
you don't have a variety of devices, this also keeps complicated chime names (like Amazon
tune paths ) out of your automation code. See the Example code at the bottom of this section.


#### Switch and Siren

Provide a list of `switch`, `siren` entities to use for chimes
and it will call the `switch.turn_on` or `siren.turn_on` calls as appropriate.

Switches are simple binary affairs, however some sirens can also have a choice of tones, volume
level and durations. The following generic chime tunings are passed to the siren.

| Chime Option   | Siren Data Field |
| -------------- | ---------------- |
| chime_tune     | tone             |
| chime_volume   | volume           |
| chime_duration | duration       |


Supernotify passes on the `data` structure exactly as it is on the regular Home Assistant actions,
see the documentation for those integrations below:

- [Siren](https://www.home-assistant.io/integrations/siren/)
- [Switch](https://www.home-assistant.io/integrations/switch/)


Switches are a little special, in that though they are binary on/off in Home Assistant, in
practice even some of the cheap 433Mhz ones can take an additional melody code, its common to
have different melodies represented by separate `switch` entities for the same underlying devices
as in this example Byron device using the [RFLink](https://www.home-assistant.io/integrations/rflink/) integration.

```yaml
- platform: rflink
  devices:
    byron_0000_01:
      name: Chime Tubular
    byron_0000_02:
      name: Chime Morning Dew
    byron_0000_03:
      name: Chime Big Ben
```
#### Scripts

Provide one or more `script` entity IDs, for example, `script.call_bell_api`.

Each script will be called with:

- `message` - from the notification
- `title`   - optional on the notification
- `chime_tune` - name of the chime if supplied
- `chime_duration` - where passed in action data or defined in chime alias
- `chime_volume` - where passed in action data or defined in chime alias

Additional variables can be configured when defining an alias using the `variables` attribute in `data`.

See also [Script](https://www.home-assistant.io/integrations/script/) in HomeAssistant documentation.

#### Alexa Media Player

NOTE: Requires the [`Alexa Media Player`](https://github.com/alandtse/alexa_media_player) integration
to be installed on Home Assistant.

Supply `media_player` entities as targets and this method will make appropriate `media_player.play_media`
action calls to them, passing the sound name provided in `tune` field.

See https://github.com/alandtse/alexa_media_player/wiki#known-available-sounds for
a list of known tunes that work with Alexa devices.

#### Alexa Devices

This supports the newer built-in [Alexa Devices](https://www.home-assistant.io/integrations/alexa_devices/)
integration introduced in 2025.

The list of sounds can be found on the [Alexa API](https://alexa.amazon.com/api/behaviors/entities?skillId=amzn1.ask.1p.sound), after authenticating, or on the [Home Assistant source code](https://github.com/home-assistant/core/blob/dev/homeassistant/components/alexa_devices/strings.json#L105). It includes a generous helping of Halloween specific sounds.

One oddity of this integration is that although it generates traditional entity IDs for notifying Alexa devices,
sending a sound ( or command ) requires a long and obscure `device_id` (a 32 character random hexadecimal pseudo-UUID).
While you can find these from the *Devices* section of the *Alexa Devices* integration config, or using the *Action*
feature of *Developer Tools* and switching to yaml mode, the easiest way is to **automatically register** all Alexa devices by using `device_discovery: True` on the method configuration. (Sometimes you may end up with odd devices like headphones or firesticks
that Alexa knows about but don't make sense for HomeAssistant usage - these can be disabled from the *Alexa Devices* integration config).

#### Example

```yaml
methods:
  chime:
    device_discovery: True
    target:
      - media_player.kitchen_echo
      - media_player.bedroom
      - ffff0000eeee1111dddd2222cccc3333 # Alexa Devices device_id
    options:
        chime_aliases:
              doorbell: #alias
                alexa_devices: # integration domain or label ( if label then domain must be a key in the config )
                    tune: amzn_sfx_cat_meow_1x_01
                media_player:
                    # resolves to media_player/play_media with sound configured for this path
                    tune: home/amzn_sfx_doorbell_chime_02
                    # entity_id list defaults to `target` of method default or action call
                    # this entry can also be shortcut as `media_player: home/amzn_sfx_doorbell_chime_02`
                media_player_alt:
                    # Not all the media players are Amazon Alexa based, so override for other flavours
                    tune: raindrops_and_roses.mp4
                    target:
                        - media_player.hall_custom
                switch:
                    # resolves to switch/turn_on with entity id switch.ding_dong
                    target: switch.chime_ding_dong
                siren_except_bedroom:
                    # resolves to siren/turn_on with tune bleep and default volume/duration
                    tune: bleep
                    domain: siren # domain must be explicit since key is label not domain and no explicit targets
                siren_bedroom:
                    # short and quiet burst for just the bedroom siren
                    domain: siren
                    tune: bleep
                    target: siren.bedroom
                    volume: 0.1
                    duration: 5
                script:
                    target: script.pull_bell_cord
                    data:
                      variables:
                        duration: 25

              red_alert:
                # non-dict defaults to a dict with a single key `tune`
                alexa_devices: scifi/amzn_sfx_scifi_alarm_04
                siren: emergency
```

With this chime config, a doorbell notification can be sent to multiple devices just
by selecting a tune.

```yaml
    - action: notify.supernotify
      data:
        message: ""
        delivery:
            chimes:
                data:
                    chime_tune: doorbell
```


### SMS

This can work with any SMS notification integration by setting the `action` value to match, for example `action: notify.mikrotik_sms`

Uses the `phone_number` attribute of recipient, and truncates message to fit in an SMS.

Since SMS sends a single message with no title, by default the message and title are combined into a single string prior to truncation. Use `title_handling` in an `options` section to change the behaviour, either message only or using the title in place of the message.

### Generic

Use to call any 'legacy' Notification action (previously known in Home Assistant as 'service' ), that is one not using the newer `NotifyEntity` model.

If action is in `notify` domain, then `message`,`title`,`target` and `data` will be
passed in the Action (Service) Data, otherwise the `data` supplied will be passed directly
as the Action Data.

```yaml
    - action: notify.supernotify
      data:
        title: "My Home Notification"
        message: "Notify via custom chat"
        delivery:
            chat_notify:
                data:
                    channel: 3456
    - action: notify.supernotify
      data:
        delivery:
            mqtt_notify:
                data:
                  topic: alert/family_all
                  payload: something happened
```

### Email

Can be used for plain or HTML template emails, and handle images as attachments or embedded HTML.

Also supports `message_html` override to supply html that will be ignored for other notification
types, and does not require templates. In this case, HTML will automatically be tagged onto the
end to include any attached images.

### Media Image

Show an image on a media player, e.g. an Alexa Show ( where that actually works, depending on model )

### Alexa

Announce, or speak, a notification using Home Assistant's built-in *Alexa Devices* integration.

The `title_handling` option can be set to `combine_message` or `replace_message` to override the default behaviour of speaking the `message`.

*Note* Home Assistant recommend sending multiple notifications to an [Alexa Device Group](https://www.amazon.co.uk/gp/help/customer/display.html?nodeId=GS8URL9U6PW8SPTA), rather than an explicit list of Alexa devices, to minimize the likelihood of Amazon rate-limiting API calls. Home Assistant managed groups work for announcements, but not speaking, and don't have the API efficiency of Alexa's own groups.

When speaking, [SSML](https://developer.amazon.com/en-US/docs/alexa/custom-skills/speech-synthesis-markup-language-ssml-reference.html) is available, for example:

- ```<say-as interpret-as="interjection">bah humbug</say-as>```
- ```<say-as interpret-as='spell-out'>hello</say-as>```
- ```<amazon:emotion name="excited" intensity="high">Activity at front door!</amazon:emotion>```
- ```<amazon:effect name='whispered'>Just a low priority notification</amazon:effect>```
- ```<prosody rate='x-slow'>Saying this slowly</prosody>```
- ```<voice name='Geraint'>hello I'm from Abergavenny</voice>```
- ```<say-as interpret-as='date'>????0922</say-as>``` ( will read as 'September 22nd' )

### Alexa Media Player

Announce a message on an Alexa Echo device using the [`alexa_media_player`](https://github.com/alandtse/alexa_media_player) integration available via [HACS](https://www.hacs.xyz).

The `title_handling` option can be set to `combine_message` or `replace_message` to override the default behaviour of speaking the `message`.

### Persistent

Place a notification on Home Assistant application screen.

Pass a notification ID

## Media support

Images can be included by:

- camera entity, as created by any [Camera Integration](https://www.home-assistant.io/integrations/camera/)
- image entity, for example an [MQTT Image](https://www.home-assistant.io/integrations/image.mqtt/), ideal for Frigate or cameras that stream to MQTT
- `snapshot_url`

Additionally a video clip can be referenced by `clip_url` where supported by a delivery method (currently mobile push only).

An optional PTZ preset can also be referenced in `data`, a PTZ delay before snapshot taken,
and a choice of `onvif` or `frigate` for the PTZ control. After the snap, an additional PTZ will be commanded to return to the `ptz_default_preset` defined for the camera.This image will taken once and then reused across all supporting delivery methods.

Some cameras, like Hikvision, add JPEG comment blocks which confuse the very simplistic media
detection in the SMTP integration, and leads to spurious log entries. Supernotify will automatically rewrite JPEGs into simpler standard forms to avoid this, and optionally `jpeg_opts` can be set, for example to reduce image quality for smaller email attachments. See the *Saving* section under **JPEG** on the [PIL Image Writer documentation[(https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#)] for the full set of options available.

```yaml
 - action: notify.supernotify
      data:
        title: "My Home Notification"
        message: "Notify with image snapshot taking close-up of vehicle on driveway"
        delivery:
            data:
                media:
                    camera_entity_id: camera.driveway
                    camera_ptz_preset: closeup
                    camera_delay: 10
                    jpeg_opts:
                      progressive: true
                      optimize: true
                      quality: 50
```

## Flexible Configuration

Delivery configuration can be done in lots of different ways to suit different configurations
and to keep those configuration as minimal as possible.

Priority order of application


| Where                                | When            | Notes                                            |
|--------------------------------------|-----------------|--------------------------------------------------|
| Action Data                          | Runtime call    |                                                  |
| Recipient delivery override          | Runtime call    |                                                  |
| Scenario delivery override           | Runtime call    | Multiple scenarios applied in no special order   |
| Delivery definition                  | Startup         | `message` and `title` override Action Data      |
| Method defaults                      | Startup         |                                                  |
| Target notification action defaults  | Downstream call |                                                  |


1. Action Data passed at runtime call
2. Recipient delivery override
3. Scenario delivery override
4. Delivery definition
5. Method defaults
6. Target notification action defaults, e.g. mail recipients ( this isn't applied inside Supernotify )

## Setup

Register this GitHub repo as a custom repo
in your [HACS]( https://hacs.xyz) configuration.

Configure in the main Home Assistant config yaml, or an included notify.yaml

See `examples` directory for working minimal and maximal configuration examples.

### Cameras

Use this for additional camera info:

* Link a `device_tracker` to the camera
  * Notifications will first check its online, then use an alternative if primary is down
* Define alternative cameras to use if first fails using `alt_camera`
* For ONVIF or Frigate cameras set up for PTZ
  * Home preset can be defined using `ptz_default_preset` so camera can be reset after taking a snapshot
  * Delay between PTZ command and snapshot can be defined using `ptz_delay`
  * Choose between ONVIF or Frigate PTZ control using `ptz_method`
    * Note that ONVIF may have numeric reference for presets while Frigate uses labels

## Delivery Method Options

All of these set by passing an `options` block in Delivery config or Method defaults.

|Option         |Methods            |Description                                                  |
|---------------|-------------------|-------------------------------------------------------------|
|chime_aliases  |chime              |Map tunes to device name or config                           |
|jpeg_opts      |mail               |Tune image grabs                                             |
|title_handling |all                |Use title rather than message, or combined title and message |
|timestamp      |all                |Add a timestamp to message.                                  |

`jpeg_opts` can also be set per runtime call by passing in the `media` block.

## Snoozing

Snoozing can be done for a set time, or notifications can be silenced until further notice ( or currently until reboot ).

### Mobile Actions

Mobile actions will be handled according to scheme:

SUPERNOTIFY_<COMMAND>_<TargetType>_

## Scenarios

Scenarios can be defined both as a set of conditions which switch on the scenario and/or as
a set of overrides to apply if the scenario is active.

For example, a scenario could be defined by conditions such as alarm panel arm state, occupancy
and time to indicate when notifications should be minimized, and then different chime sounds
could be selected or deliveries switched off.

Scenarios can override specific delivery configurations, general media configuration (such as setting a camera, or specifying which alert sound to use for a mobile push ). A scenario have a
default `delivery_selection` basis of `implicit`, where the scenario inherits all the default
deliveries, or have this switched off by overriding `delivery_selection` to `explicit` or `fixed` (both do the same thing) in which case only the deliveries mentioned in the scenario
are included.

For more on the conditions, see the [ Home Assistant Conditions documentation](https://www.home-assistant.io/docs/scripts/conditions/) since the conditions are all evaluated at time of
notification by the standard Home Assistant module.


### Example Scenarios

This scenario could be used to select more obtrusive notifications, like email or Alexa announcements,
from a combination of conditions, hence simplifying separate notification calls, and providing
one place to tune multiple notifications.

```yaml
more_attention:
        alias: time to make more of a fuss
        condition:
          condition: and
          conditions:
            - not:
                - condition: state
                  entity_id: alarm_control_panel.home_alarm_control
                  state: disarmed
            - condition: time
              after: "21:30:00"
              before: "06:30:00"
```

In this example, selecting the scenario by name in a notification call switches on
a set of delivery methods, which saves repetitive declaration in many notification calls. Delivery
Selection is made `implicit` so not switching off any other deliveries that would have applied.

```yaml
red_alert:
      delivery_selection: implicit
      delivery:
        chime_red_alert:
        upstairs_siren:
        downstairs_siren:
      media:
        camera_entity_id: camera.porch
```

Delivery selection can also be passed in the `data` of an action call, in which case it can
also be `fixed`, which disables scenarios from enabling or disabling deliveries and leaves it solely
to defaults or what's listed in the action call.

Conditions aren't essential for scenarios, since they can also be switched on by a notification.

For example in this case, where the `home_security` and `garden` scenarios are explicitly
triggered, and so any overrides declared in those scenarios will be applied. The `constrain_scenarios`
prevents any scenario other than `unoccupied` or the ones explicitly applied here ( to switch off all
other scenarios, use `NULL`).

```yaml
  - action: notify.supernotifier
    data:
        title: Security Notification
        message: '{{state_attr(sensor,"friendly_name")}} triggered'
        priority: high
        apply_scenarios:
          - home_security
          - garden
        constrain_scenarios:
          - unoccupied
```

Individual deliveries can be overridden, including the content of the messages using `message_template` and `title_template`.
The templates are regular HomeAssistant `jinja2`, and have the same context variables available as the scenario conditions (see below ). In the example below, Alexa can be made to whisper easily without having to mess with the text of every notification, and this scenario could also have conditions applied, for example to all low priority messages at night.

```yaml
  scenarios:
    emotional:
      delivery:
        alexa:
          data:
            title_template: '<amazon:emotion name="excited" intensity="medium">{{notification_message}}</amazon:emotion>'
```

Multiple scenarios can be applied, in the order provided, and each template will be applied in turn to the results of the previous template. So in the example below, you could apply both the *whisper* and *emotion* Amazon Alexa markup to the same message, or add in some sound effects based on any of the conditions.

A blank `message_template` or `title_template` can also be used to selectively switch off one of those fields for a particular delivery, for example when sending a notification out via email, push and Alexa announcement.

### Additional variables for conditions

Scenario and DeliveryMethod conditions have access to everything that any other Home Assistant conditions can
access, such as entities, templating etc. In addition, Supernotify makes additional variables
automatically available:

|Template Variable              |Description                                                       |
|-------------------------------|------------------------------------------------------------------|
|notification_priority          |Priority of current notification, explicitly selected or default  |
|notification_message           |Message of current notification                                   |
|notification_title             |Title of current notification                                     |
|applied_scenarios              |Scenarios explicitly selected in current notification call        |
|required_scenarios             |Scenarios a notification mandates to be enabled or else suppressed|
|constrain_scenarios            |Restricted list of scenarios                                      |
|occupancy                      |One or more occupancy states, e.g. ALL_HOME, LONE_HOME            |


## Tips

### Message formatting

To send a glob of html to include in email, set `message_html` in action data. This will be ignored
by other delivery methods that don't handle email. This can be also be used to have a notification
with only a title ( that gets picked up for mobile push, alexa and other brief communications ) with
a much more detailed body only for email.

Use `data_template` to build the `data` dictionary with Jinja2 logic from automations or scripts.
