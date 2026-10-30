---
tags:
  - transport
  - gotify
---
# Gotify Transport Adaptor

| Transport ID | Source      | Requirements | Optional |
| ------------ | ----------- | ------------ | -------- |
| `gotify` | :material-github:[`gotify.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/gotify.py) | :material-github: [homeassistant-gotify](https://github.com/1RandomDev/homeassistant-gotify) HACS integration | - |

## Motivation

[Gotify](https://gotify.net) is a self-hosted push notification server. The Gotify transport adds, beyond a plain
`notify` call:

* SuperNotify's priority mapped to Gotify's 0–10
* A tap-through URL, defaulting to a [notification level action](../usage/mobile_actions.md#notification-level-actions)
* An expanded image (`bigImageUrl`), from a URL or a camera snapshot
* Markdown rendering
* An Android intent opened when the message arrives

## Priority Mapping

| SuperNotify | Gotify |
|-------------|--------|
| `critical`  | 10     |
| `high`      | 7      |
| `medium`    | 5      |
| `low`       | 2      |
| `minimum`   | 0      |

## Data Keys

* `gotify_priority` — `0` to `10`, overriding the mapping; a number outside that is brought into range
* `gotify_click` — URL opened when the notification is tapped
* `gotify_image_url` — URL of an image shown expanded, used ahead of a snapshot
* `gotify_attach_image` — use the camera snapshot as the expanded image (default `false`)
* `gotify_markdown` — render the message as Markdown (default `false`)
* `gotify_intent_url` — Android intent URL opened when the message arrives, needing the Gotify app's
  *Intent Action Permission*

The image is sent as a URL, so the Gotify app must be able to reach Home Assistant's media folder, through the
external URL when away from home. Other `data` isn't passed on, since the integration only reads the priority
and extras.

## Configuration

```yaml title="Home Assistant Configuration"
notify:
  - platform: gotify
    name: gotify
    url: http://gotify.local
    token: !secret gotify_token
```

```yaml title="Supernotify Configuration"
delivery:
  gotify_alarm:
    transport: gotify
    action: notify.gotify          # only needed if discovery doesn't find it
    data:
      gotify_click: "https://ha.example.com/lovelace/security"
      gotify_attach_image: true
      gotify_markdown: true
```

## Example Call

```yaml
action: supernotify.notify
data:
  message: "**Front door** open - check the dashboard"
  priority: critical
  delivery: gotify_alarm
  media:
    camera_entity_id: camera.front_door
```

## Discovery

**Delivery (explicit selection).** SuperNotify looks for a `notify` action from the HACS integration. If found
and no `gotify` delivery is defined, a `gotify` delivery is generated automatically. Gotify has no target to
recognise, so it's only used when named in `delivery`, a scenario or a recipient, or if you set `inclusion: default`
on your own delivery to send every notification there.

## Notes

* The HACS integration logs a failure to reach the Gotify server rather than raising an error, so a notification
  is recorded as delivered even if Gotify didn't receive it. Check the Home Assistant log if messages go missing.
* Without a title, the integration uses "Home Assistant".

## References

* [homeassistant-gotify](https://github.com/1RandomDev/homeassistant-gotify) HACS integration
* [Gotify message extras](https://gotify.net/docs/msgextras)
