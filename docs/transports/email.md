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

!!! note
    The Home Assistant [SMTP](https://www.home-assistant.io/integrations/smtp/) integration for e-mail doesn't allow
    priority to be set.

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
| img               | Snapshot image attachment, with `url` and `desc` fields                         |

The `preheader` defaults to a minimum 100 characters packed with `&#847;&zwnj;&nbsp;` to force e-mail clients
not to dig into the message contents when showing a preview in the in-box.

Where the image is snapped rather than being only a URL, it will be included as an attachment and
an `cid:XXXX` URL generated to point to the attachment name.

!!! info
    The additional `data` options for Google Mail (`cc`,`bcc`,`from`) are not yet supported.

## Default Delivery

A default Delivery called `DEFAULT_email` will be automatically generated for Email transport if no explicit ones
created, since this is the new standard HomeAssistant notification provider. If you don't want to use it, then
use configuration as below, or configure your own delivery for the transport.

```yaml
transports:
  email:
    disabled: false
```
