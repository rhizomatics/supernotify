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


Can be used for plain or HTML template emails, and handle images as attachments or embedded HTML. Automatically configured if there's already an SMTP integration.

!!! note
    The Home Assistant [SMTP](https://www.home-assistant.io/integrations/smtp/) integration for e-mail doesn't allow priority to be set.

## Pre-generated HTML

The `data` section of the notification can have a `message_html` supplied for html that will be used in place of the standard `message` for HTML emails and ignored for other notification types. This does not require templates, see the [Restart Email Recipe](../recipes/restart_email.md) for a simple example. In this case, HTML will automatically be tagged onto the end to include any attached images. The `data` can be configured as part of the fixed configuration, or in the `data` of the action call.

## HTML Templates

HTML templates use the standard Home Assistant Jinja2 [Templating](https://www.home-assistant.io/docs/configuration/templating) with access to entity states, additional filters etc.

Padding to nudge e-mail clients from reading too deeply into the e-mail for in-box summaries can be tuned with `preheader_blank` and `preheader_length` configuration in the transport `options`. The other useful option is `strict_template` to switch on or off the stricter
Jinja2 template validation.

### Configuration

Supernotify ships with a built in template, `default.html.j2` which can be used by using `template: default.html.j2` in the `data` section. This shouldn't be edited directly, since changes will get overwritten by future releases. Instead, write your own, or amended versions of [`default.html.j2`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/default_templates/email/default.html.j2) and put
it into a custom template directory, usually inside Home Assistant's `\config` directory. Templates can live in this directory, or in an `email` subdirectory ( the top-level is for templates that could be used with any transport, and `email` only for this one).

```yaml title="Example Supernotify Configuration"
- name: SuperNotify
  platform: supernotify
  template_path: /config/templates/supernotify
```

### Template Variables

Supernotify also adds an `alert` variable for context of the current notification, with these values:

| Attribute         | Description                                                                                |
|-------------------|--------------------------------------------------------------------------------------------|
| message           | Notification message                                                                       |
| title             | Notification title                                                                         |
| preheader         | Invisible `div` contents at top of html used to show info below heading                    |
| priority          | Notification priority                                                                      |
| envelope          | Delivery Envelope (complex nested object)                                                  |
| subheading        | Defaults to "Home Assistant Notification"                                                  |
| server            | Access to `name`,`language`,`internal_url` and `external_url` of this HomeAssistant server |
| preformatted_html | HTML supplied to the notify action, for example by an Automation                           |
| action_url        | Action URL for mobile action                                                               |
| action_url_title  | Title for the Action URL                                                                   |
| img               | Snapshot image attachment, with `url` and `desc` fields                                    |

The `preheader` defaults to a minimum 100 characters packed with `&#847;&zwnj;&nbsp;` to force e-mail clients
not to dig into the message contents when showing a preview in the in-box.

### Image Attachments

Where the image is snapped rather than being only a URL, it will be included as an attachment and
an `cid:XXXX` URL generated to point to the attachment name.

!!! info
    The additional `data` options for Google Mail (`cc`,`bcc`,`from`) are not yet supported.

## Default Delivery

A default Delivery called `DEFAULT_email` will be automatically generated for Email transport if no explicit ones created, using the first available SMTP integration if one is present. If you don't want to use it, then use configuration as below, or configure your own delivery for the transport.

```yaml
transports:
  email:
    disabled: false
```

## Reference

### Home Assistant Core
- [SMTP Integration](https://www.home-assistant.io/integrations/smtp/)
    - [Open Issues](https://github.com/home-assistant/core/issues?q=is%3Aissue%20label%3A%22integration%3A%20smtp%22%20state%3Aopen)
- [Templating](https://www.home-assistant.io/docs/configuration/templating/)
### Home Assistant Other
- [Mastering Dynamic HTML Email Alerts in Home Assistant: Secure SMTP & Custom Content](https://newerest.space/home-assistant-dynamic-html-email-alerts-secure-smtp-custom-content/)
### General
- [MailChimp HTML Email Template Guide](https://templates.mailchimp.com)
- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/stable/templates/)
