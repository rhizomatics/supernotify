# Index

## Built-in Transport Adaptors

{{ pagetree(siblings) }}

## Customizing Transports

### Options

Most transport adaptors support an additional set of options, some common ones for handling titles
or suppressing URLs, and some specific to a transport.

In this example, image attachments for emails get tuned ( since these are commonly needed, the email
delivery transport defaults to always having `progressive` and `optimize` being true, unless explicitly overridden)

```yaml
 email:
        delivery_defaults:
          action: notify.smtp
          options:
            jpeg_opts:
              progressive: true
              optimize: true
              quality: 50
```

### Table of Options

All of these set by passing an `options` block in Delivery config or Transport defaults.

| Option            | Transports | Description                                                  |
|-------------------|------------|--------------------------------------------------------------|
| chime_aliases     | chime      | Map tunes to device name or config                           |
| jpeg_opts         | mail       | Tune image grabs                                             |
| title_handling    | all        | Use title rather than message, or combined title and message |
| timestamp         | all        | Add a timestamp to message.                                  |
| simplify_text     | all        | Remove some common symbols that can trip up voice assistants |
| strip_urls        | all        | Remove URLs from message and title                           |
| message_usage     | all        | Combine message and title, default title                     |
| target_categories | all        | Which targets to pass, e.g. `entity_id`,`email`,`device_id`  |
| unique_targets    | all        | Don't pass targets already used in this notification         |
| target_include_re | all        | Only use targets matching these regular expressions          |

`jpeg_opts` can also be set per runtime call by passing in the `media` block.
