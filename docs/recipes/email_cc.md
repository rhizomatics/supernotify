# Recipe - Email CC

## Purpose

Copy in an e-mail address on all notifications, for example as a message archive.

## Implementation

Define a target on the `email` transport, and set the `target_definition` to `merge`,
so these addresses are combined with the addresses on the notification.

## Example Configuration
```yaml
    transports:
      email:
        delivery_defaults:
            target_definition: merge
            target:
                - mailarchive@mymail.com
```

## Variations

### Other transports
This will work identically for any transport, there's nothing email specific in how it works

### Multiple e-mail deliveries

You have both `html_email` and `plain_email` deliveries, and only want to cc the plain ones.

In this case, define the defaults at delivery level rather than transport level.

```yaml
    deliveries:
      plain_email:
        action: notify.smtp
        delivery_defaults:
            target_definition: merge
            target:
                - mailarchive@mymail.com
```