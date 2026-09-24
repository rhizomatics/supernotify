# Selection Rules

Source: https://supernotify.rhizomatics.org.uk/latest/configuration/selection_rules/

Several transport options use **Selection Rules** which allow a flexible set of inclusion or exclusion values, which can be plain text or regular expressions.

## Options Using Selection Rules

- `data_keys_select`
- `device_area_select`
- `device_label_select`
- `device_manufacturer_select`
- `device_os_select`
- `device_model_select`
- `target_select`

See [Options Table](https://supernotify.rhizomatics.org.uk/latest/reference/options/index.md) for description and where these can be used.

## Rule Definitions

Simple Single Include

```yaml
  options:
    data_keys_select:
      include: My.*Key
```

Simple Include List

```yaml
  options:
    data_keys_select:
      include:
        - enabled
        - value
        - zig.*
```

Simple Exclude List

```yaml
  options:
    data_keys_select:
      exclude:
        - duration
        - volume
```

A more complex case is filtering nested mappings, common in Home Assistant YAML and JSON. When `exclude` is a mapping, a null value excludes that key; a dict value keeps the key but recurses into it with the same tree logic:

Advanced Exclusion

```yaml
  options:
    data_keys_select:
      exclude:
        data:             # descend into `data`
          attachment:     # exclude `attachment` from `data`
          video:          # exclude `video` from `data`
          media:          # descend into `data.media`
            url:          # exclude `url` from `data.media`
```

**Named sub-filter** — any non-reserved key in the config dict is a full `data_keys_select` config applied recursively to that key's value:

```yaml
  options:
    data_keys_select:
      include: [message, data]      # top-level include
      data:                         # sub-filter for `data`
        include: [attachment, push]
```

Both forms can be combined freely and nest to any depth.
