---
tags:
  - frigate
  - recipe
  - mobile_push
  - cctv
  - frigate
  - ios
  - apple
  - macos
  - blueprint
title: Fix Apple Notifications from Frigate Blueprint
description: Fix broken images when sending mobile push notifications to Apple devices
---

# Recipe - Fix Apple Notifications from Frigate Blueprint

## Purpose

The [Frigate Blueprint](https://github.com/SgtBatten/HA_blueprints/tree/6cffba9676ccfe58c5686bd96bf15a8237e1a3f9/Frigate_Camera_Notifications) is used to create mobile push notifications, with the image embedded
and links to the Frigate UI.

The blueprint creates a `clip.mp4` link for iOS devices, however the [Frigate API Docs](https://docs.frigate.video/integrations/api/recording-clip-camera-name-start-start-ts-end-end-ts-clip-mp-4-get) recommended not doing this for iOS compatibility reasons, and using the `m8u` action link instead.

This results in broken images for notifications, on iPhones, Macs or other Apple push notification targets.

![Example Broken Image](../assets/images/broken_image_notification.png){width=400}

## Implementation

Simplest way to fix this is to remove the `data` section keys with the mp4, and
while doing that, can also remove the Android specific keys that you won't
need if only iOS devices to notify.

This uses the `data_keys_select` configuration, originally designed for the
Generic Transport toolbox, and extended to Mobile Push in v1.16.0.

## Example Configuration

```yaml title="Example Delivery Definition"
...
delivery:
    ...
    apple_push:
      alias: Push notifications to iPhones, iPads and Macs
      transport: mobile_push
      options:
        data_keys_select:
          exclude:
            data:
              attachment:
              video:
              clickAction: # iOS uses 'url'
```
## Variations and Alternatives
- Hack the blueprint instead, and re-edit it when updating it
- Create separate deliveries for Android and Apple devices

### Apple/Android specific deliveries

```yaml
deliveries:
  apple_push:
    transport: mobile_push
    options:
    device_manufacturer_select:
        include:
        - Apple
  android_push:
    transport: mobile_push
    options:
    device_manufacturer_select:
        exclude:
        - Apple
```
