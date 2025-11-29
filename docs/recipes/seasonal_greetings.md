---
tags:
  - xmas
  - holiday
  - scenario
  - recipe
  - condition
---
# Recipe - Seasonal Greetings

## Purpose

Add a Xmas, Halloween or whatever else flavour to messages;

## Implementation

A scenario using Home Assistant date conditions that applies a message template with Amazon SSML only to specific delivery config,
in this case one called `alexa_general`, and to the email text.

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
              message_templage '{{notification_message}} Ho Ho Ho!'
       alexa_general:
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
            data:
              message_template: '{{notification_message}}<break time="1s"><say-as interpret-as="interjection">hip hip hooray</say-as>'

```
