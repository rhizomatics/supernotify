---
tags:
  - faq
  - support
  - help
title: Frequently Asked Questions
description: Answers to support queries
---
# Frequently Asked Questions

## Target Selection

**Q**: If I define a `label_id` and an `area_id`, and in that area I have 3 devices, is the `label_id` treated as an `AND`? (so it will send to just devices in `label_id` that have `label_id`), or an `OR`, (so it sends to all devices that are in `area_id`, as well as all devices in the system that have `label_id`?)

**A**: It works as an OR selector - give me all everything that is in area X OR has label Y, so all the `area_id`,`floor_id` and `label` targets all add up to one big list. This is part of the standard Home Assistant [target selectors](https://www.home-assistant.io/docs/blueprint/selectors/#target-selector) which happens outside of Supernotify, and works the same for all integrations.

**Q**: How do I send a notification to only 3 of my Alexa speakers and not the rest.

**A**: There are a few ways of doing this

 Option 1 - Use the Home Assistant [Target Selector](https://www.home-assistant.io/docs/blueprint/selectors/#target-selector) on the `supernotify.notify` action to pick the speakers by their **Area**, **Floor** or **Label**.

 Option 2 - Create a separate *Delivery* (YAML only at present) for these speakers, and list them as targets. Then when setting up notifications, pick this delivery from the list.

```yaml
alexa_inform:
    alias: Ask all the Alexas apart from bedrooms to speak the notification
    transport: alexa_devices
    target:
    - notify.kitchen_alexa_speak
    - notify.living_room_flex_speak
    - notify.studio_speak
```
