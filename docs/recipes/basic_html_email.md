# Recipe - Simple HTML Email

## Purpose

Enrich email with a html message without impacting notifications sent via SMS, Alexa announcements etc

## Implementation

To send a glob of html to include in email, set `message_html` in action data. This will be ignored
by other delivery methods that don't handle email. This can be also be used to have a notification
with only a title ( that gets picked up for mobile push, alexa and other brief communications ) with
a much more detailed body only for email.

Use `data_template` to build the `data` dictionary with Jinja2 logic from automations or scripts.

## Example

See [Home Assistant Restart Notification](restart_email.md) recipe for a simple application.
