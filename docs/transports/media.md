---
tags:
  - transport
  - alexa
  - media_player
---
# Media Player Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `media` | :material-github:[`media_player.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/media_player.py) | - | :simple-homeassistantcommunitystore: [Alexa Media Player Integration](https://github.com/alandtse/alexa_media_player), other :material-home-assistant: [Media Player Integration](https://www.home-assistant.io/integrations/?cat=media-player) |

## Discovery

**Delivery (explicit selection).** If at least one `media_player` entity exists in the house and
no `media` delivery is defined, a `media` delivery is generated automatically — but since
`media_player` targets vary too much between devices to safely assume a default, it only fires
when selected explicitly (`data: {data: {delivery: [media]}}` or a scenario), not by default.

Show an image on a media player, for example an Amazon Echo Show device, or play an audio file or other content on any media player.

Pass the content link in using the `snapshot_url` value in the notification `data` section. Message and title fields will be ignored. Override the `image` value by also setting `media_content_type` in `data`.

## Example

```yaml title="Example Notification"
- action: supernotify.notify
  data:
    message: ""
    delivery:
      media:
        target:
            - media_player.kitchen_alexa
        data:
            snapshot_url: https://mycctvserver/doorbell/snapshot.jpeg
```

The resulting action call from the adaptor looks like:

```yaml
service: media_player.play_media
data:
  media_content_id: https://mycctvserver/doorbell/snapshot.jpeg
  media_content_type: image
  entity_id: media_player.kitchen_alexa
```

## Playing audio or other content

Set `media_content_id` in the delivery `data` to play anything the media player accepts, rather than an image - for example an mp3 alert sound on a Google Cast or Sonos speaker, a video clip or a `media-source://` item.

- A relative URL like `/local/sounds/alarm.mp3` (a file in `config/www/sounds`) is made absolute using the Home Assistant external URL, so that the speaker can fetch it
- Absolute URLs and `media-source://` ids are passed through unchanged
- `media_content_type` defaults to `music` when `media_content_id` is given, override it if the player needs something else, e.g. `audio/mpeg`
- `media_content_id` takes priority over any `snapshot_url` or camera image, and no image is grabbed
- `announce` and `enqueue` are passed through as for images

```yaml title="Example Notification"
- action: supernotify.notify
  data:
    message: ""
    delivery:
      media:
        target:
            - media_player.kitchen_speaker
        data:
            media_content_id: /local/sounds/alarm.mp3
            announce: true
```

The speaker has to be able to reach the URL, so it must be on the local network or publicly available, and some devices, like Google Cast, reject self-signed certificates.

Amazon Echo devices can't play arbitrary audio files this way. For those, use the built-in sounds via the [Chime Transport Adaptor](chime.md), which is also the better fit for short tunes mapped to named aliases across different kinds of device.

## Alexa Media Player

It can be used to show an image, for example a CCTV event snapshot, on an Alexa Show device using the **Alexa Media Player** custom integration.

There are a few limitations and considerations with this use:

- It uses the `alexapy` integration, calling an *unofficial* `/api/background-image` API on the Echo device, which Amazon could change at any time with new Echo firmware, albeit that hasn't happened in years.
- Not all Alexa Show devices seem to support this
- The image must be on an `https` URL with valid certificate.
- The `image` value required by Alexa Media Player is not one of the recommended values in the Home Assistant documentation.


## References

* [Set Echo Show Background](https://github.com/alandtse/alexa_media_player/wiki#set-echo-show-background) on Alexa Media Player Documentation
* [Home Assistant Media Player Integration](https://www.home-assistant.io/integrations/media_player/)
* [Available Media Player Integrations for Home Assistant](https://www.home-assistant.io/integrations/?cat=media-player)
