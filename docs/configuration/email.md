---
tags:
  - smtp
  - email
  - google mail
  - aws ses
  - action
---
# e-Mail Notifications

## Configuration

If you have e-mail configured in Home Assistant, you can include it in Supernotify by setting up an e-mail delivery:

```yaml title="Supernotify config"
- name: Supernotify
  platform: supernotify
  delivery:
      plain_email:
        transport: email
```

The `email` for `transport` must match the `name` given to a [SMTP](https://www.home-assistant.io/integrations/smtp/) notify integration in your config, which will look like this Amazon Simple Email Service example:

```yaml title="SMTP config"
- name: email
  platform: smtp
  ...
```

## Targets

There are several ways of supplying targets:

### Built-into the SMTP Notify configuration

The `recipient` field is a mandatory field. Not recommended, other than as a back-up address if no other target provided.

### Supernotify Delivery

```yaml title="Supernotify Config"
- name: Supernotify
  platform: supernotify
  delivery:
      plain_email:
        transport: email
        target:
          - joe@mcdoe.com
          - billy@weeschool.edu
```

### Supernotify Recipient

This has the advantage that e-mail addresses can be defined in one place, and you can send targeted
email notifications in automations by using the `person` entity instead.

```yaml title="Supernotify Config"
- name: Supernotify
  platform: supernotify
  ...
  recipients:
    - person: person.joe_mcdoe
      email: joe@mcdoe.com
    - person: person.billy_mcdoe
      email: billy@weeschool.edu
```

### On Action Call

Whatever method has been defined, you can always override it on an notification action call

```yaml title="Example Message"
  - action: notify.supernotify
    data:
        message: Something went off in the basement
        target: john@mcdoe.co.bn
```

## Example SMTP Configuration

### Amazon Simple Email Service

In this example, the username and password live separately in the `secrets.yaml` file, see [Storing Secrets](https://www.home-assistant.io/docs/configuration/secrets/) for more on that.

[Amazon SES](https://aws.amazon.com/ses/) is a cheap and easy to use service, with the overhead of having to set up an Amazon AWS service if you don't have one already. The free tier saves money for new AWS accounts, although you can send 1000 emails for $0.10 USD so it doesn't save all that much ( more if you send attachments like images, though only $0.12 USD per Gb at 2025 prices.)

```yaml title="SMTP config"
- name: email
  platform: smtp
  port: 587
  timeout: 30
  encryption: starttls
  sender: hass@myhouse.org
  recipient: admin@myhouse.org
  server: email-smtp.eu-west-2.amazonaws.com
  username: !secret aws_smtp_key
  password: !secret aws_smtp_secret
```

!!! warning
    Amazon AWS can be a *very* cheap way of getting services like e-mail and storage with its
    pay-as-you-go serverless model, 10c a month buys a decent amount of emails.

    However, it can also be *exceedingly* expensive if abused or mis-configured.

    Follow the [Security Best Practices](https://repost.aws/knowledge-center/security-best-practices), including MFA for the main account, and giving Home Assistant
    a dedicated IAM user that can only access the services it really needs, with the account ID
    and secret key kept secure.

    Add a [budget](https://blog.thecloudengineers.com/p/aws-budgets-for-beginners-how-to) and
    [cost alerts](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/monitor_estimated_charges_with_cloudwatch.html) if you're still worried!

### Google Mail

See the [Home Assistant Example](https://www.home-assistant.io/integrations/smtp/#google-mail)
