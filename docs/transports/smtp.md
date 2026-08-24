---
tags:
  - transport
  - email
  - smtp
  - html_email
---
# SMTP Transport Adaptor

| Transport ID | Source                                                                                                                                | Requirements | Optional                                                                                                                                                                                                     |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------|--------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `smtp`      | :material-github:[`smtp.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/smtp.py) | -            |  |

## Features

Alternative to the `email` integration which avoids using the built in Home Assistant, with the same functionality except no overhead of pre-registering email addresses, introduced in mid-2026 Home Assistant as part of the Notify Entity integration.

See [email](email.md) for more details, for example use of HTML or templates.

In addition to reverting to the previous simpler Home Assistant usage, it also offers:

### Priority

Envelope priority is mapped to common header fields used for internet mail:

- Priority
- Importance
- X-Priority
- X-MSMail-Priority

### Message-ID

`Message-Id` in email header ties back to notification ID and delivery name

## Example Config

Connections default to `STARTTLS` over port 587, though can be changed to other ports or without encryption. This will work with Amazon SES, local mail relays etc.

```yaml
transports:
     smtp:
        connection:
          host: smtp.local.net
          port: 587
          encryption: starttls
          username: postie
          password: blackandwhitecat
          verify_ssl: false
        delivery_defaults:
          options:
            sender: hass@local.net
            sender_name: Your Friendly Home Assistant
            default_title: Home Assistant Notification
```

In addition, all of the options from `email` integration are available, such as for tuning PNG attachments or preheaders for message previews.


## Roadmap

Initially this only preserves the original easier to use functionality of Home Assistant SMTP prior to the enforcement of pre-registering every e-mail address as an `entity`, and mapping envelope priority to common headers.

It is anticipated that this will also open up more features, such as modern email features like DKIM.
