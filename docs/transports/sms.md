# SMS Transport

This can work with any SMS integration that follows Home Assistant Notification model.

Configure which one by setting the `action` value to match, for example `action: notify.mikrotik_sms`

Uses the `phone_number` attribute of recipient, and truncates message to fit in an SMS.

Since SMS sends a single message with no title, by default the message and title are combined into a single string prior to truncation. Use `title_handling` in an `options` section to change the behaviour, either message only or using the title in place of the message.
