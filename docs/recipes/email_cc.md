# Recipe - Email CC

## Purpose

Copy in an e-mail address on all notifications, for example as a message archive.

## Implementation

Define a target on the `email` transport, and set the `target_usage` to `merge_delivery`,
so these addresses are combined with the addresses on the notification.

## Example Configuration
```yaml
    transports:
      email:
        delivery_defaults:
            target_usage: merge_delivery
            target:
                - mailarchive@mymail.com
```

## Variations

### Other transports
This will work identically for any transport, there's nothing email specific in how it works

### Multiple e-mail deliveries

You have both `html_email` and `plain_email` deliveries, and only want to cc the plain ones.

In this case, define the defaults at delivery level rather than transport level.

The `target_usage: merge_delivery` setting means that the `mailarchive@mymail.com` address will
only be added if there's already an e-mail being sent with other targets.

```yaml
    deliveries:
      plain_email:
        action: notify.smtp
        delivery_defaults:
            target_usage: merge_delivery
            target:
                - mailarchive@mymail.com
```

If you want to always have the email sent, even if there are no other recipients, then set  `target_usage: merge_always`.

Alternatively, set up a dedicated delivery like this, which will always send off to `mailarchive@mymail.com`
and nobody else.

```yaml
    deliveries:
      email_archive:
        action: notify.smtp
        delivery_defaults:
            target_usage: fixed
            target:
                - mailarchive@mymail.com
```
