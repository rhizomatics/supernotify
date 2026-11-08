# Recipe - Email CC

Source: https://supernotify.rhizomatics.org.uk/latest/recipes/email_cc/

## Purpose

Copy in an e-mail address on all notifications, for example as a message archive.

## Implementation

Define a target on the `email` transport, and set the `target_usage` to `merge_delivery`, so these addresses are combined with the addresses on the notification.

## Example Configuration

Change the `email` transport under *Settings → Devices & services → Supernotify*, and in its *Delivery Defaults*, set the **Target usage** to `merge_delivery` and add `mailarchive@mymail.com` as a **Custom target**. As YAML, that is the transport's:

```yaml
delivery_defaults:
  target_usage: merge_delivery
  target:
    - mailarchive@mymail.com
```

## Variations

### Other transports

This will work identically for any transport, there's nothing email specific in how it works

### Multiple e-mail deliveries

You have both `html_email` and plain `email` deliveries, and only want to cc the plain ones.

In this case, set the target on the delivery rather than the transport.

The `target_usage: merge_delivery` setting means that the `mailarchive@mymail.com` address will only be added if there's already an e-mail being sent with other targets.

```yaml
    delivery:
      email:
        transport: email
        target_usage: merge_delivery
        target:
          - mailarchive@mymail.com
```

If you want to always have the email sent, even if there are no other recipients, then set `target_usage: merge_always`.

Alternatively, set up a dedicated delivery like this, which will always send off to `mailarchive@mymail.com` and nobody else.

```yaml
  delivery:
    email_archive:
      transport: email
      inclusion: default
      target_usage: fixed
      target:
        - mailarchive@mymail.com
```

Only when the delivery is selected

`merge_always` and a dedicated delivery like `email_archive` only send when their delivery is selected for the notification. A delivery whose **Inclusion** is `explicit` or `scenario`, or any delivery without an `inclusion` of its own, or from its transport's *Delivery Defaults*, when **Default Inclusion** is `explicit` in the integration's *Delivery Control* options, is only selected when a notification names it, or a scenario switches it on - so not for every notification. Give it `inclusion: default`, as above, to have it used for every notification.
