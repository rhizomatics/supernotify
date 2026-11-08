---
tags:
  - recipe
  - people
  - email
  - telegram
  - recipient
  - ui
title: Easy Notifications for Someone Who Isn't a Home Assistant User
description: Add a Supernotify recipient by name, with an e-mail address and a Telegram chat id, and notify them by e-mail and Telegram with a single target
---
# Recipe - Notify Someone Who Isn't a Home Assistant User

## Purpose

Keep someone in the loop who has no Home Assistant account, like a relative, a neighbour keeping an eye on the house, or a cleaner. Notify them by e-mail and Telegram, without repeating their address and chat id in every automation.

## Implementation

A **Recipient** added by name in the integration, with their e-mail address, and their Telegram chat id as a custom target. No YAML is needed.

Supernotify gives them a recipient id, `user.` followed by their name in lower case with underscores, and a *Notify Entity*, `notify.recipient_` followed by the same. Either can be used as a target, and stands in for everything set up for them - the e-mail delivery gets their e-mail address, and the Telegram delivery gets their chat id.

## Prerequisites

- The [email transport](../transports/email.md) with a mail server connection, of its own or reused from the SMTP integration
- The [Telegram Bot](https://www.home-assistant.io/integrations/telegram_bot) integration, with the recipient's chat id allowed. The [telegram transport](../transports/telegram.md) is set up automatically once it is there
- Their Telegram chat id - one way to find it is to have them message the bot, and look at the `telegram_text` event in *Developer Tools → Events*

## Adding the Recipient

Go to *Settings → Devices & services → Supernotify → Add recipient*.

1. Give their **Name**, such as `Granny Smith`, leaving **Person** and **User** empty
2. Fill in:
    - **E-mail address** - `granny@example.com`
    - **Custom targets** - `telegram_chat_id:215678938`

That's it. They're listed under the integration as *Recipient - Granny Smith*, with `notify.recipient_granny_smith` and `switch.supernotify_recipient_granny_smith` entities.

## Sending Notifications

Address them by their recipient id:

```yaml
action: supernotify.notify
data:
  title: Sunday lunch
  message: Roast at 1pm
  target: user.granny_smith
```

or their notify entity, from anything that takes a standard Home Assistant notify target:

```yaml
action: notify.send_message
target:
  entity_id: notify.recipient_granny_smith
data:
  title: Sunday lunch
  message: Roast at 1pm
```

Either sends an e-mail to `granny@example.com`, and a Telegram message to chat `215678938`. Their recipient id can also be mixed in with other targets, such as `person.bob`.

A notification with no `target` goes to every recipient, so they get those too. To keep them off one delivery, use **Advanced - Delivery Overrides** on their recipient - see [Disabling a Delivery for One Recipient](../configuration/people.md#disabling-a-delivery-for-one-recipient). To pause them altogether for a while, turn off their switch.

## Variations

- Add a **Phone number** too, for an SMS delivery
- Other custom targets work the same way, such as a `discord_channel:` for the [discord transport](../transports/discord.md)

## See Also

- [People](../configuration/people.md)
- [Targets](../usage/targets.md)
