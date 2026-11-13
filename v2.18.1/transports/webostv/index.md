# LG webOS TV Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/webostv/

## Motivation

Shows notifications as a toast on LG webOS TVs, through the Home Assistant [LG webOS TV](https://www.home-assistant.io/integrations/webostv/#notifications) integration.

The integration gives each TV a notify action of its own, such as `notify.living_room_tv`, rather than a notify entity, so on their own the TVs can't be reached by area. This transport targets each TV's `media_player` entity instead, and finds its notify action, so a TV can be reached by area, floor, label or device as well as by its entity.

## Features

- No set up: a `webostv` delivery is made whenever the LG webOS TV integration is set up.
- Only sent to a TV when it is targeted, directly or by its area, floor, label or device, so a TV isn't interrupted by every notification in the house.
- TVs that are off, or unavailable, are skipped, as the integration can't reach them.
- Only the message is shown. The title is used only when there's no message.

## Configuration

Nothing is needed. Target the TV, or where it is:

```yaml
action: notify.supernotify
data:
  message: Dinner is ready
  target:
    area_id: lounge
```

Targeting the whole ground floor reaches every TV on it that's on, as well as anything else there, such as Alexa devices:

```yaml
action: notify.supernotify
data:
  message: Someone's at the door
  target:
    floor_id: ground
```

## webOS TV Data Keys

- `icon` — path to an image file on the Home Assistant host, shown as the toast's icon. Any other `data` is left out, since the integration takes nothing else

```yaml
action: notify.supernotify
data:
  message: Dinner is ready
  target:
    area_id: lounge
  data:
    icon: /config/www/dinner.png
```

## Notes

- The notify action is named by the integration after the TV, as it was called when set up. After renaming the TV, its notify action keeps the old name until the integration is reloaded.
- A TV that is skipped because it's off isn't an error, so a delivery `fallback:` isn't used for it. To reach someone another way when the TV is off, use a [scenario](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/index.md) with a condition on the TV's state.
