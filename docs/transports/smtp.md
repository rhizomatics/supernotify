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

## Roadmap

Initially this only preserves the original easier to use functionality of Home Assistant SMTP prior to the enforcement of pre-registering every e-mail address as an `entity`.

It is anticipated that this will also open up more features, such as use of importance or priority, and supporting modern email features like DKIM.
