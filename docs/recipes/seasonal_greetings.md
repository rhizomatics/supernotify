---
tags:
  - xmas
  - holiday
  - scenario
  - recipe
  - condition
description: Use a Supernotify scenario to add a seasonal note to notifications
---
# Recipe - Seasonal Greetings

## Purpose

Add a Xmas, Halloween or whatever else flavour to messages;

## Implementation

A scenario using Home Assistant date conditions that applies a message template with Amazon SSML only to specific delivery config, in this case one called `alexa_general`, and to the email text.

The `select: false` is used so that the delivery will be overridden only if its has already
been selected before this scenario was applied, otherwise the scenario would add on these
deliveries to every notification during the date condition period.

## Example Configuration
Use a scenario with a condition to identify when in a date range.

The speech markup requires use of the `speak` rather than `announce` entities provided by Alexa Devices integration.

```yaml
scenarios:
    xmas:
      alias: Christmas season
      conditions:
        condition: or
        conditions:
          - "{{ (12,24) <= (now().month, now().day) <= (12,31) }}"
          - "{{ (1,1) <= (now().month, now().day) <= (1,1) }}"
      delivery:
       email_general:
            data:
              message_template: '{{notification_message}} Ho Ho Ho!'
       alexa_general:
            select: false
            data:
              message_template: '{{notification_message}}<break time="1s"><say-as interpret-as="interjection">bah humbug</say-as>'

    halloween:
      alias: Spooky season
      conditions:
        condition: and
        conditions:
          - "{{ (10,31) == (now().month, now().day) }}"
      delivery:
          alexa_general:
            select: false
            data:
              message_template: '{{notification_message}}<break time="1s"><audio src="soundbank://soundlibrary/horror/horror_04"/>'

    birthdays:
      alias: Family birthdays
      conditions:
        condition: or
        conditions:
          - "{{ (5,23) == (now().month, now().day) }}"
          - "{{ (11,9) == (now().month, now().day) }}"
      delivery:
       alexa_general:
            select: false
            data:
              message_template: '{{notification_message}}<break time="1s"><say-as interpret-as="interjection">hip hip hooray</say-as>'

```

## Variations

The [Chime Transport Adaptor](../transports/chime.md) has lots more ways of doing this.

Set up aliases for common chimes, and a secondary seasonal version, in the Chime transport defaults:

```yaml
transports:
  chime:
    device_discovery: true
    device_domain: alexa_devices
    delivery_defaults:
      options:
        chime_aliases:
          doorbell:
            alexa_devices:
              tune: amzn_sfx_doorbell_chime_02
            switch:
              target: switch.chime_ding_dong
          xmas_doorbell:
            alexa_devices: christmas_05
```

Then create a date condition scenario, that overrides the chime alias for your `doorbell_rang` delivery:

```yaml
scenarios:
    xmas:
      alias: Christmas season
      conditions:
        condition: or
        conditions:
          - "{{ (12,24) <= (now().month, now().day) <= (12,31) }}"
          - "{{ (1,1) <= (now().month, now().day) <= (1,1) }}"
      delivery:
        doorbell_rang:
          select: false
          data:
            chime_tune: xmas_doorbell
```
