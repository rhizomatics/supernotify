---
tags:
  - email
  - scenario
  - html_email
  - recipe
title: Basic HTML Formatted Email Notifications
description: Send a basic HTML formatted email notification from Home Assistant using Supernotify
---
# Recipe - Simple HTML Email

## Purpose

Enrich email with a html message without impacting notifications sent via SMS, Alexa announcements etc

## Implementation

To send a glob of html to include in email, set `message_html` in action data. This will be ignored
by other delivery transports that don't handle email. This can be also be used to have a notification
with only a title ( that gets picked up for mobile push, alexa and other brief communications ) with
a much more detailed body only for email.

```yaml title="Example Action Call"
- action: notify.supernotify
      data:
        title: "Motion Detection at Back Door"
        message: "Motion has been detected at the back door"
        message_html: "Motion was last detected at {{{{ states.binary_sensor.back_door_pir.last_changed.isoformat() }} near the <a href="http://192.168.10.10/cctv/back_door_cam">back door</a>"
```


## Example

See [Home Assistant Restart Notification](restart_email.md) recipe for a simple application.
