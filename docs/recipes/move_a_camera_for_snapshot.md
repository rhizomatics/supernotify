---
tags:
  - frigate
  - recipe
  - cctv
  - onvif
  - ptz
title: Camera PTZ For Notifications
description: Move a CCTV camera to a preset PTZ position, take a snapshot image for notifications, then move the camera back.
---
# Recipe - Move a Camera for Snapshot

## Purpose

When an alert is generated from a location, for example a Frigate zone, or a motion PIR, make a CCTV
camera move and/or zoom to that place, before taking a snapshot image and attaching it to an email
or mobile push message.

This requires what's known as a "PTZ" camera, for pan-tilt-zoom, though some fisheye cameras can
do something similar without motors, and some cameras have only zoom, or only pan/tilt. You will
also need to set up labelled PTZ pre-sets, which can be done through the camera's own setup
screens, DVR or CCTV app.

## Implementation

Define the camera and presets in the `cameras` section. By default, an ONVIF command will be sent
for the PTZ preset, although in this case overridden to use Frigate's interface.

## Example Configuration

```yaml
cameras:
    - camera: camera.courtyard
      # Use frigate for PTZ rather than ONVIF commands
      ptz_method: frigate
      # Wait 5 seconds before taking a snapshot to give camera time to move
      ptz_delay: 5
      # After a PTZ movement has occurred, return the camera back to this preset
      ptz_default_preset: "Preset 1"
```

## Example Action Call

```yaml
  - action: notify.supernotify
    data:
        title: 'ALERT: {{ state_attr(motion_sensor,"friendly_name") }}'
        message: Motion at night in {{ state_attr(motion_sensor,"friendly_name")
        data:
            media:
                camera_entity_id: camera.courtyard
                camera_ptz_preset: "Preset 2"
```

## Variations

### Backup camera

If your main camera sometimes goes down, but there's another one that can be used, define the `device_tracker`
( usually provided by a network device like Unifi or OPNSense ) to determine if its online, and configure the alternate camera. This can be combined with the other PTZ config.

```yaml
cameras:
    - camera: camera.courtyard
      # use a device tracker, like a Unifi LAN one, to check camera is on
      device_tracker: device_tracker.courtyard_camera
      # if the camera is down, use the doorbell camera instead
      alt_camera: camera.doorbell
```


## Further Reading

* [Frigate Camera Configuration](https://docs.frigate.video/configuration/cameras/)
* [SecurityCamCenter PTZ Topics](https://securitycamcenter.com/?s=ptz)
* Home Assistant
    * [Device Tracker Integration](https://www.home-assistant.io/integrations/device_tracker/)
    * [Camera Integration](https://www.home-assistant.io/integrations/camera/)
