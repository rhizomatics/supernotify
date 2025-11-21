---
tags:
  - transport
  - sms
---
# SMS Transport Adaptor

| Transport ID         | Source      | Requirements | Optional |
| -------------------- | ----------- | ------------ | -------- |
| `sms` | :material-github:[`sms.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/sms.py) | - | :material-home-assistant: [SMS Notification Integrations](https://www.home-assistant.io/integrations/?search=sms&cat=notifications), :simple-homeassistantcommunitystore: [Mikrotik SMS Integration](https://github.com/jeyrb/hass_mikrotik_sms) |


This can work with any SMS integration that follows Home Assistant Notification model.

Configure which one by setting the `action` value to match, for example `action: notify.mikrotik_sms`

Uses the `phone_number` attribute of recipient, and truncates message to fit in an SMS.

Since SMS sends a single message with no title, by default the message and title are combined into a single string prior to truncation. Use `title_handling` in an `options` section to change the behaviour, either message only or using the title in place of the message.
