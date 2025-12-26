---
tags:
  - transport
  - email
  - smtp
  - html_email
---
# Email Transport Adaptor

| Transport ID | Source                                                                                                                                | Requirements | Optional                                                                                                                                                                                                     |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------|--------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `email`      | :material-github:[`email.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/email.py) | -            | :material-home-assistant: [SMTP Integration](https://www.home-assistant.io/integrations/smtp/), :material-home-assistant: [Google Mail Integration](https://www.home-assistant.io/integrations/google_mail/) |


Can be used for plain or HTML template emails, and handle images as attachments or embedded HTML.

## Pre-generated HTML

The `data` section of the notification can have a `message_html` supplied for html that will be used
in place of the standard `message` for HTML emails and ignored for other notification types. This does not require templates, see the [Restart Email Recipe](../recipes/restart_email.md) for a simple example. In this case, HTML will automatically be tagged onto the
end to include any attached images.

## HTML Templates

HTML templates use the standard Home Assistant [Templating](https://www.home-assistant.io/docs/configuration/templating) with access to entity states, additional filters etc.

Supernotify also adds an `alert` variable for context of the current notification, with these values:

| Attribute         | Description                                                                     |
|-------------------|---------------------------------------------------------------------------------|
| message           | Notification message                                                            |
| title             | Notification title                                                              |
| preheader         | Invisible `div` contents at top of html used to show info below heading         |
| priority          | Notification priority                                                           |
| envelope          | Delivery Envelope (complex nested object)                                       |
| subheading        | Defaults to "Home Assistant Notification"                                       |
| server            | Access to `name`,`internal_url` and `external_url` of this HomeAssistant server |
| preformatted_html | HTML supplied to the notify action, for example by an Automation                |
| img               | Snapshot image attachment                                                       |

!!! info
    The additional `data` options for Google Mail (`cc`,`bcc`,`from`) are not yet supported.
