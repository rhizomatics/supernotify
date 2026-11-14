# RFC 0012 - Prompted Notifications

Use the built-in Home Assistant GenAI integrations to generate notification content or delivery method from prompts.

## Actions

Offer a `content_prompt` and a `delivery_prompt` as top level fields:

```yaml
action: supernotify.notify
data:
  message: Something went off in the basement
  delivery_prompt: Send this to mobile devices, with email as a back up for anyone who doesn't have one. Make it high priority if nobody home
```

```yaml
action: supernotify.notify
data:
  content_prompt: Create a detailed description of what happened to trigger this, and a separate concise spoken description
```

## Scenarios

Use a scenario to set `content_prompt` and/or `delivery_prompt`.  The prompt will be given the condition variables as context and can generate config like a scenario, including target and delivery selection.
