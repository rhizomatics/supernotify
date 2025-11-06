# Recipe - Alexa Whispering

## Purpose

Make all low priority Alexa announcements in a whisper.

## Implementation

A scenario using Home Assistant conditions that applies a message template with Amazon SSML only to specific delivery config,
in this case one called `alexa_inform`.

## Example Configuration

```yaml
  routine:
      alias: regular low level announcements
      condition:
        condition: and
        conditions:
          - "{{notification_priority in ['low']}}"

      delivery:
        plain_email:
        apple_push:
        alexa_inform:
          data:
            message_template: '<amazon:effect name="whispered">{{notification_message}}</amazon:effect>'
```

## Variations

Use similar scenarios to have a noise ( a bell, or a spooky Halloween noise ) embedded in messages, make
the voice more or less emotional, change the voice personality / nationality or even have it sung.
