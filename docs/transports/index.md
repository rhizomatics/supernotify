# Transport Adaptors

These are the notification transport adaptors built into Supernotify:

<style>
.pagetree-functions { display: none; }
</style>
{{ pagetree(siblings) }}

## Customizing Transports

### Options

Most transport adaptors support an additional set of options, some common ones for handling titles or suppressing URLs, and some specific to a transport.

In this example, image attachments for emails get tuned ( since these are commonly needed, the email
delivery transport defaults to always having `progressive` and `optimize` being true, unless explicitly overridden)

```yaml
transports:
  email:
    delivery_defaults:
      action: notify.smtp
      options:
        jpeg_opts:
          progressive: true
          optimize: true
          quality: 50
        png_opts:
          optimize: true
```
## Entities

Each loaded Transport Adaptor has a `switch.supernotify_transport_XXXX` entity in Home Assistant, with its configuration and
current state as attributes. Turning it off, whether from a dashboard, Developer Tools or an automation, suppresses all of
the deliveries that use that transport, and turning it on again re-enables them. The delivery switches keep their own state
throughout. See [Delivery Entities](../configuration/deliveries.md#entities).

### Table of Options

All of these are set by passing an `options` block in Delivery config or Transport defaults. See the
[Options Reference](../reference/options.md) for the full, generated list of common and transport-specific
options, their types, examples and descriptions - and [Default Options](../reference/transports.md#default-options)
for the actual default value each transport sets.

`jpeg_opts` can also be set per runtime call by passing in the `media` block.

Options typed as [Selection Rules](../configuration/selection_rules.md) (e.g. `device_os_select`, `target_select`)
share a common flexible syntax - see that page for the full set of forms.
