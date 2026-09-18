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

Transport Adaptors are exposed as `sensor.supernotify_transport_XXXX` entities in Home Assistant, with the configuration and
current state. All of the deliveries that use a given transport can be disabled, or re-enabled, by changing the
state of the entity, whether via Developer Tools or another automation.

### Table of Options

All of these are set by passing an `options` block in Delivery config or Transport defaults. See the
[Options Reference](../configuration/options.md) for the full, generated list of common and transport-specific
options, their types, examples and descriptions - and [Default Options](../developer/transports.md#default-options)
for the actual default value each transport sets.

`jpeg_opts` can also be set per runtime call by passing in the `media` block.

Options typed as [Selection Rules](../configuration/selection_rules.md) (e.g. `device_os_select`, `target_select`)
share a common flexible syntax - see that page for the full set of forms.
