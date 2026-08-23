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

Alternative to the `email` integration which avoids using the built in Home Assistant, with the same functionality except no overhead of pre-registering email addresses, introduced in mid-2026 Home Assistant as part of the Notify Entity integration.

See [email](email.md) for more details, for example use of HTML or templates.

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
```

In addition, all of the options from `email` integration are available, such as for tuning PNG attachments or preheaders for message previews.


## Roadmap

Initially this only preserves the original easier to use functionality of Home Assistant SMTP prior to the enforcement of pre-registering every e-mail address as an `entity`.

It is anticipated that this will also open up more features, such as use of importance or priority, and supporting modern email features like DKIM.
