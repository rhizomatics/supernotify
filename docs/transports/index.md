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

All of these set by passing an `options` block in Delivery config or Transport defaults.

| Option               | Transports | Description                                                                |
|----------------------|------------|----------------------------------------------------------------------------|
| chime_aliases        | chime      | Map tunes to device name or config                                         |
| jpeg_opts            | mail       | Tune image grabs                                                           |
| png_opts             | mail       | Tune image grabs                                                           |
| message_usage        | all        | Combine message and title, default title                                   |
| simplify_text        | all        | Remove some common symbols that can trip up voice assistants               |
| strip_urls           | all        | Remove URLs from message and title                                         |
| target_categories    | all        | Which targets to pass, e.g. `entity_id`,`email`,`device_id`                |
| target_include_re    | all        | Only use targets fully matching these regular expressions                  |
| unique_targets       | all        | Don't pass targets already used in this notification                       |
| data_keys_include_re | generic    | List of values or regex full match patterns allowed in `data` block        |
| data_keys_exclude_re | generic    | List of values or regex full match patterns not allowed in `data` block    |
| handle_as_domain     | generic    | Treat the action call in same way as a known domain                        |
| strict_template      | email      | Fail template if Jinja2 issues found when `true`, render anyway if `false` |

`jpeg_opts` can also be set per runtime call by passing in the `media` block.
