---
tags:
  - mqtt
  - archiving
  - configuration
  - debugging
  - housekeeping
description: Archive notifications in Supernotify, including for debugging notification rules or formatting
---
# Notification Archiving

Debugging notification rules, scenarios etc is much easier when the `Notification` object, complete with its debug trail, is archived.

This preserves not just the notification data, but also key context like occupancy, and the decisions made during the process on which scenarios, deliveries etc to select.

Key fields to check if something doesn't seem right:

- `selected_deliveries` - What was selected by the action, scenarios or delivery configuration
- `deliveries` - what happened to each delivery, `delivered_envelopes`,`undelivered_envelopes` or `no_envelopes`

A housekeeping job will run automatically each night to prune notifications older than your configured sell-by date.

!!! tip
    Use the [Studio Code Server](https://github.com/hassio-addons/addon-vscode) Home Assistant app
    to search and browse the archived notifications.

## Example Configuration

This example switches on both file system and MQTT topic archiving. Additional options (`mqtt_qos`, `mqtt_retain`) are available if needed to fine tune the MQTT publication.

```yaml
notify:
  - name: my_notifications
    platform: supernotify
    archive:
      enabled: true
      file_retention_days: 4
      file_path: config/archive/supernotify
      mqtt_topic: notifications/supernotify
```

## Example Notification

```yaml
{
  "created": "2025-11-04T15:09:21.375872+00:00",
  "debug_trace": [
    "A Car was detected on the Driveway camera.",
    null,
    {
      "tag": "1762268908.791668-ksvmf7",
      "group": "driveway-frigate-notification",
      "color": "#03a9f4",
      "subject": "",
      "image": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/thumbnail.jpg",
      "video": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/master.m3u8",
      "clickAction": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/clip.mp4",
      "ttl": 0,
      "priority": "high",
      "alert_once": false,
      "notification_icon": "mdi:homeassistant",
      "sticky": false,
      "channel": "alarm_stream",
      "car_ui": false,
      "fontsize": "large",
      "position": "center",
      "duration": 10,
      "transparency": "0%",
      "interrupt": false,
      "subtitle": "",
      "url": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/clip.mp4",
      "attachment": {
        "url": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/master.m3u8",
        "content-type": "application/vnd.apple.mpegurl"
      },
      "push": {
        "sound": {
          "name": "default",
          "volume": 1.0
        },
        "interruption-level": 1
      },
      "entity_id": "camera.driveway",
      "actions": [
        {
          "action": "URI",
          "title": "View Clip",
          "uri": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/clip.mp4",
          "icon": "",
          "destructive": false
        },
        {
          "action": "URI",
          "title": "View Snapshot",
          "uri": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/snapshot.jpg",
          "icon": "",
          "destructive": false
        },
        {
          "action": "silence-automation.generate_apple_event_for_frigate_driveway",
          "title": "Silence New Notifications",
          "uri": "silence-automation.generate_apple_event_for_frigate_driveway",
          "icon": "",
          "destructive": true
        }
      ]
    },
    null,
    {},
    {
      "override_disable_deliveries": [],
      "override_enable_deliveries": [],
      "scenario_enable_deliveries": [
        "plain_email",
        "alexa_announce",
        "apple_push",
        "high_chime_alert"
      ],
      "default_enable_deliveries": [],
      "scenario_disable_deliveries": [
        "html_email",
        "alexa_inform",
        "chime_person",
        "chime_dog",
        "chime_doorbell",
        "chime_unknown_vehicle",
        "chime_known_vehicle",
        "chime_red_alert",
        "upstairs_siren",
        "downstairs_siren"
      ]
    }
  ],
  "_message": "A Car was detected on the Driveway camera.",
  "target": [],
  "_title": null,
  "id": "3deb818c-b990-11f0-a89d-000c29e67c70",
  "snapshot_image_path": null,
  "delivered": 0,
  "errored": 0,
  "skipped": 0,
  "delivery_error": null,
  "data": {
    "tag": "1762268908.791668-ksvmf7",
    "group": "driveway-frigate-notification",
    "color": "#03a9f4",
    "subject": "",
    "image": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/thumbnail.jpg",
    "video": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/master.m3u8",
    "clickAction": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/clip.mp4",
    "ttl": 0,
    "alert_once": false,
    "notification_icon": "mdi:homeassistant",
    "sticky": false,
    "channel": "alarm_stream",
    "car_ui": false,
    "fontsize": "large",
    "position": "center",
    "duration": 10,
    "transparency": "0%",
    "interrupt": false,
    "subtitle": "",
    "url": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/clip.mp4",
    "attachment": {
      "url": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/master.m3u8",
      "content-type": "application/vnd.apple.mpegurl"
    },
    "push": {
      "sound": {
        "name": "default",
        "volume": 1.0
      },
      "interruption-level": 1
    },
    "entity_id": "camera.driveway"
  },
  "priority": "high",
  "message_html": null,
  "required_scenario_names": [],
  "applied_scenario_names": [],
  "constrain_scenario_names": [],
  "delivery_selection": "implicit",
  "delivery_overrides_type": "NoneType",
  "delivery_overrides": {},
  "action_groups": [
    "alarm_panel",
    "lights"
  ],
  "recipients_override": null,
  "media": {
    "snapshot_url": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/thumbnail.jpg",
    "clip_url": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/master.m3u8"
  },
  "debug": false,
  "actions": [
    {
      "action": "URI",
      "title": "View Clip",
      "uri": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/driveway/clip.mp4",
      "icon": "",
      "destructive": false
    },
    {
      "action": "URI",
      "title": "View Snapshot",
      "uri": "https://home.43acaciaave.org/api/frigate/notifications/1762268908.791668-ksvmf7/snapshot.jpg",
      "icon": "",
      "destructive": false
    },
    {
      "action": "silence-automation.generate_apple_event_for_frigate_driveway",
      "title": "Silence New Notifications",
      "uri": "silence-automation.generate_apple_event_for_frigate_driveway",
      "icon": "",
      "destructive": true
    }
  ],
  "delivery_results": {},
  "delivery_errors": {},
  "selected_delivery_names": [
    "high_chime_alert",
    "apple_push",
    "alexa_announce",
    "plain_email"
  ],
  "enabled_scenarios": {
    "high_alert": {
      "name": "high_alert",
      "enabled": true,
      "alias": "make a fuss if alarm armed or high priority",
      "media": null,
      "delivery_selection": "implicit",
      "action_groups": [
        "alarm_panel",
        "lights"
      ],
      "delivery": {
        "plain_email": null,
        "alexa_announce": null,
        "apple_push": null,
        "high_chime_alert": null
      },
      "default": false
    }
  },
  "selected_scenario_names": [
    "high_alert"
  ],
  "people_by_occupancy": [],
  "suppressed": "DUPE",
  "occupancy": {
    "home": [
      {
        "person": "person.joe_mctoe",
        "email": "joe@mctoefamily.net",
        "phone_number": "+4377332010983",
        "delivery": {},
        "mobile_devices": [
          {
            "manufacturer": "Apple",
            "model": "iPhone15,2",
            "mobile_app_id": "mobile_app_joephonepro",
            "device_tracker": "device_tracker.joephonepro",
            "device_id": "a0591c4af99b6a4037f7346f390e9918",
            "device_name": "jPhonePro"
          }
        ],
        "mobile_discovery": true,
        "user_id": "cbed93ea6eac7d575710dc519e5e3dc1",
        "state": "home"
      },
      {
        "person": "person.jane_mctoe",
        "email": "jane@mctoefamily.org",
        "delivery": {},
        "mobile_devices": [
          {
            "manufacturer": "Apple",
            "model": "iPhone13,2",
            "mobile_app_id": "mobile_app_jane_s_iphone_13",
            "device_tracker": "device_tracker.jane_s_iphone_13",
            "device_id": "71ba297a58a3b601e1646c54d0e23dbf",
            "device_name": "Jane's iPhone 13"
          }
        ],
        "mobile_discovery": true,
        "user_id": "1cba227f2c0cb65cfd3cafde6ce0c4d8",
        "state": "home"
      }
    ],
    "not_home": []
  },
  "condition_variables": {
    "occupancy": [
      "ALL_HOME"
    ],
    "applied_scenarios": [],
    "required_scenarios": [],
    "constrain_scenarios": [],
    "notification_priority": "high",
    "notification_message": "A Car was detected on the Driveway camera.",
    "notification_title": ""
  }
}
```
