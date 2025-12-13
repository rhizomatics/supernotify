---
tags:
  - scenario
  - recipe
  - cctv
  - appdaemon
description: Send advanced notifications from the popular AppDaemon add-on for Home Assistant
---
# Recipe - AppDaemon Cameras

## Purpose

Call supernotify from *AppDaemon* python code, triggered by a driveway magnetic detector, and including an image from CCTV camera, and additional config for mobile actions.

Before taking the image, move the camera to a PTZ preset for a better view.

## Implementation

The `hass` API in AppDaemon is used to call the Supernotify platform, first building up
an action data dictionary.

## Example Code

```python
    action_data={
                  "priority": priority,
                  "message_html": rendered_template,
                  "apply_scenarios":["cctv","driveway"],
                  "media": {
                    "camera_entity_id": "camera.driveway",
                    "camera_ptz_preset": "driveway_entrance",
                    "snapshot_url":f"/api/frigate/notifications/{event_id}/snapshot.jpg",
                    "clip_url":f"/api/frigate/notifications/driveway/{event_id}/clip.mp4",
                  },
                  "actions":[
                    { "action_url_title":"Go to Camera",
                      "action_url":"http://10.4.6.43/cameras/driveway/view"
                    }
                  ]
    }

    try:
        self.hass.call_service(
            "notify/supernotify",
            message=message,
            title=title,
            data=action_data)
```
