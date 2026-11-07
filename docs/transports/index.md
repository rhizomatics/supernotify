# Transport Adaptors

These are the notification transport adaptors built into Supernotify:

<style>
.pagetree-functions { display: none; }
</style>
{{ pagetree(siblings) }}

## Customizing Transports

Transports are set up in the integration, not YAML. Go to *Settings → Devices & services → Supernotify*, where
every transport in use is listed already, to change it, or switch it off with **Enabled**. **Add transport** sets up
one that needs configuring before it can be used, such as [generic](generic.md) with its action, or
[chime](chime.md) with its aliases - it lists those not in use yet whose Home Assistant integration is installed.

A transport's form has:

- **Enabled**, to switch it off without removing it, and **Alias**
- **Connection**, only for a transport that makes its own connection, like [email](email.md) - the mail server's
  host, port, encryption, username, password, timeout and certificate check. The password is never shown, and
  left empty, the one set already is kept
- **Delivery Defaults**, the defaults for its deliveries, the same as `delivery_defaults` in YAML:
    - **Debug**, to wait for the result of each action its deliveries call, and record it
    - **Action**, for a transport whose action is configured rather than fixed or found, such as generic
    - **Inclusion** and **Priority**
- **Delivery Defaults - Targets**:
    - **Target usage**, how the targets below are used alongside a notification's own - see
      [Controlling Targets](../configuration/deliveries.md#controlling-targets)
    - **Targets** and **Custom targets**, chosen as in the `supernotify.notify` action
- **Delivery Defaults - Advanced**, all as YAML:
    - **Options**, the transport's own options, and **Extra Data**
    - **Other delivery defaults**, for anything else, such as `occupancy`, `conditions`, `template` or `title`
- **Advanced**, with **Load**, which leaves the transport out altogether when off, with no deliveries or switch. If
  disabled, the transport will have to be re-added with **Add transport** if needed in future

So a YAML example elsewhere in this documentation, under `transports:`, is entered on that transport's form - its
`delivery_defaults` `options` under **Options**, and so on.

Deprecated settings, such as `device_domain` directly on a transport rather than in its options, raise a repair
naming them. Saving the transport's form moves them to their replacements.

!!! note "Transports from YAML"
    Transports used to be set under `transports:` in YAML. From version `2.18.0` those are imported into the
    integration when it starts, and a repair asks for them to be removed from the YAML, where they are ignored
    from then on.

### Options

Most transport adaptors support an additional set of options, some common ones for handling titles or suppressing URLs, and some specific to a transport.

In this example, entered as the email transport's **Action** and **Options**, image attachments for emails get tuned ( since these are commonly needed, the email
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

Each loaded Transport Adaptor has a `switch.supernotify_transport_XXXX` entity in Home Assistant, listed under its transport in the integration, with its configuration and
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
