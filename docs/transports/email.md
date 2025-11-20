---
tags:
  - transport
  - email
  - html_email
---
# Email Transport Adaptor

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
