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

| Option                     | Type      | Transports | Description                                                                  |
|----------------------------|-----------|------------|------------------------------------------------------------------------------|
| chime_aliases              | mapping   | chime      | Map tunes to device name or config                                           |
| jpeg_opts                  | mapping   | mail       | Tune image grabs                                                             |
| png_opts                   | mapping   | mail       | Tune image grabs                                                             |
| preheader_blank            | str       | mail       | HTML code used to pack the pre-header with blanks for HTML email             |
| preheader_length           | int       | mail       | Minimum size to pack the pre-header with blanks for HTML email               |
| message_usage              | str       | all        | Combine message and title, default title                                     |
| simplify_text              | bool      | all        | Remove some common symbols that can trip up voice assistants                 |
| strip_urls                 | bool      | all        | Remove URLs from message and title                                           |
| target_categories          | list      | all        | Which targets to pass, e.g. `entity_id`,`email`,`device_id`                  |
| target_select              | Selection | all        | Only use targets fully matching these regular expressions                    |
| unique_targets             | bool      | all        | Don't pass targets already used in this notification                         |
| data_keys_select           | Selection | generic    | Prune `data` block by including/excluding values or by regex pattern.        |
| handle_as_domain           | bool      | generic    | Treat the action call in same way as a known domain                          |
| raw                        | bool      | generic    | Don't apply domain specific `data` handling and pruning rules                |
| strict_template            | bool      | email      | Fail template if Jinja2 issues found when `true`, render anyway if `false`   |
| device_discovery           | bool      | all        | Switch automatic device discovery on or off for delivery configuration       |
| device_domain              | list      | all        | One or more Home Assistant domains to discover devices, e.g. `alexa_devices` |
| device_os_select           | Selection | all        | Choose device models in device discovery                                     |
| device_manufacturer_select | Selection | all        | Choose device manufactures in device discovery                               |
| device_os_select           | Selection | all        | Choose device operating systems in device discovery                          |
| device_label_select        | Selection | all        | Choose devices by label in device discovery                                  |
| device_area_select         | Selection | all        | Choose devices by Home Assistant area in device discovery                    |

`jpeg_opts` can also be set per runtime call by passing in the `media` block.

#### Selections

Selections have a common flexible form, and can have simple strings or regular expressions. Inclusion or
exclusion can be single values or lists. If not explicitly include or exclude, then include assumed.

```yaml title="Simple Include"
device_os_select: iOS
```

```yaml title="Simple Include List"
device_os_select:
  - iOS
  - MacOS
```

```yaml title="Explicit Include List"
device_os_select:
  include:
  - iOS
  - MacOS
```

```yaml title="Explicit Exclude List"
device_os_select:
  exclude:
  - iOS
  - MacOS
```

```yaml title="Everything"
device_os_select:
  include: .*Pixel.*
  exclude:
  - iOS
  - MacOS
```
