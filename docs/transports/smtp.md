---
tags:
  - transport
  - email
  - smtp
  - html_email
---
# SMTP Transport Adaptor

`smtp` is a deprecated alias for the [email](email.md) transport - any existing `transport: smtp` deliveries or `transports: smtp: ...` config keep working unchanged, but new configuration should use `transport: email` with the `direct_smtp` option instead. See [email](email.md) transport, and its `direct_smtp` option, to bypass the built-in limited [SMTP Integration](https://www.home-assistant.io/integrations/smtp/).
