---
tags:
  - transport
  - email
  - smtp
  - html_email
---
# Email Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `email` | :material-github:[`email.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/email.py) | - | :material-home-assistant: [SMTP Integration](https://www.home-assistant.io/integrations/smtp/), :material-home-assistant: [Google Mail Integration](https://www.home-assistant.io/integrations/google_mail/) |


Can be used for plain or HTML template emails, and handle images as attachments or embedded HTML.

Also supports `message_html` override to supply html that will be ignored for other notification
types, and does not require templates. In this case, HTML will automatically be tagged onto the
end to include any attached images.

HTML templates have an `alert` variable for context.

| Attribute         | Description                                                                     |
|-------------------|---------------------------------------------------------------------------------|
| title             | Notification title                                                              |
| envelope          | Delivery Envelope                                                               |
| subheading        | Defaults to "Home Assistant Notification"                                       |
| server            | Access to `name`,`internal_url` and `external_url` of this HomeAssistant server |
| preformatted_html | HTML supplied to the notify action, for example by an Automation                |
| img               | Snapshot image attachment                                                       |

!!! info
    The additional `data` options for Google Mail (`cc`,`bcc`,`from`) are not yet supported.
