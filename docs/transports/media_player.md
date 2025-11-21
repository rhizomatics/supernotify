---
tags:
  - transport
  - alexa
---
# Media Player Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `media` | :material-github:[`media_player.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/media_player.py) | - | :simple-homeassistantcommunitystore: [Alexa Media Player Integration](https://github.com/alandtse/alexa_media_player), other :material-home-assistant: [Media Player Integration](https://www.home-assistant.io/integrations/?cat=media-player) |


Show an image or other content on a media player, e.g. for an example an Amazon Echo Show device.

Pass the content link in using the `snapshot_url` value in the notification `data` section. Message and title fields will be ignored. Override the `image` value by also setting `media_content_type` in `data`.

The resulting action call from the adaptor looks like:

```yaml
service: media_player.play_media
data:
  media_content_id: https://mycctvserver/doorbell/snapshot.jpeg
  media_content_type: image
  entity_id: media_player.kitchen_alexa
```

If you want to send a sound to the media player, try the much more functional [Chime Transport Adaptor](chime.md).

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
