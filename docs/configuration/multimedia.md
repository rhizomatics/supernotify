---
tags:
  - email
  - mobile_push
  - cctv
  - mqtt
---
# Images, Streaming and Cameras

## Images and Video

These are most commonly used with *Mobile Push* and *Email* delivery transports.

Images can be included by:

- camera entity, as created by any [Camera Integration](https://www.home-assistant.io/integrations/camera/)
- image entity, for example an [MQTT Image](https://www.home-assistant.io/integrations/image.mqtt/), ideal for Frigate or cameras that stream to MQTT
- `snapshot_url` to grab from any HTTP(S) address

Additionally a video clip can be referenced by `clip_url` where supported by a transport (currently mobile push only).

The media content type will be automatically determined from the grabbed image.

### PTZ ( Pan, Tilt, Zoom ) Camera Support

Supernotify can ask a camera to move and zoom to a pre-set position before an image snapshot is taken. So for
example, if a person rings the doorbell, a camera could zoom in to take a close-up for the notification.

Set the (optional) PTZ preset referenced in the `data` section, whether in transport, delivery or scenario config,
or in the notify `action` call. Additionally, a PTZ delay can be set to wait for camera movement before snapshot taken,
and a choice of `onvif` or `frigate` for the PTZ control. After the snap, an additional PTZ will be commanded to return to the `ptz_default_preset` defined for the camera.This image will taken once and then reused across all supporting delivery transports.

### Automatically Fixing Camera Issues

Some cameras, like Hikvision, add JPEG comment blocks which confuse the very simplistic media
detection in the SMTP integration, and leads to spurious log entries.

Supernotify will automatically rewrite JPEGs into simpler standard forms to avoid this, and optionally `jpeg_opts` can be set, for example to reduce image quality for smaller email attachments.

See the *Saving* section under **JPEG** on the [PIL Image Writer documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#)] for the full set of options available.

### Example Action

```yaml
 - action: notify.supernotify
      data:
        title: "My Home Notification"
        message: "Notify with image snapshot taking close-up of vehicle on driveway"
        delivery:
            data:
                media:
                    camera_entity_id: camera.driveway
                    camera_ptz_preset: closeup
                    camera_delay: 10
                    jpeg_opts:
                      progressive: true
                      optimize: true
                      quality: 50
```

### Cameras

Use this for additional camera info:

* Link a `device_tracker` to the camera
  * Notifications will first check its online, then use an alternative if primary is down
* Define alternative cameras to use if first fails using `alt_camera`
* For ONVIF or Frigate cameras set up for PTZ
  * Home preset can be defined using `ptz_default_preset` so camera can be reset after taking a snapshot
  * Delay between PTZ command and snapshot can be defined using `ptz_delay`
  * Choose between ONVIF or Frigate PTZ control using `ptz_transport`
    * Note that ONVIF may have numeric reference for presets while Frigate uses labels
* Configuration documentation for [Camera Schema](../developer/schemas/Camera_Definition.md).
