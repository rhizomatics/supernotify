# Recipe - Alexa Whispering

Source: https://supernotify.rhizomatics.org.uk/latest/recipes/alexa_whisper/

## Purpose

Make all low priority Alexa announcements in a whisper.

## Implementation

A scenario using Home Assistant conditions that applies a message template with Amazon SSML only to specific delivery config, in this case one called `alexa_devices_speak_all`.

## Example Configuration

```yaml
scenarios:
  routine:
      alias: regular low level announcements
      conditions: "{{notification_priority in ['low']}}"

      delivery:
        email:
        mobile_push:
        alexa_devices_speak_all:
          data:
            message_template: '<amazon:effect name="whispered">{{notification_message}}</amazon:effect>'
```

## Variations

Use similar scenarios to have a noise ( a bell, or a spooky Halloween noise ) embedded in messages, make the voice more or less emotional, change the voice personality / nationality or even have it sung.
