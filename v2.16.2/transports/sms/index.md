# SMS (Text Messaging) Transport Adaptor

Source: https://supernotify.rhizomatics.org.uk/latest/transports/sms/

| Transport ID | Source                                                                                                           | Requirements | Optional                                                                                                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sms`        | [`sms.py`](https://github.com/rhizomatics/supernotify/blob/main/custom_components/supernotify/transports/sms.py) | -            | [SMS Notification Integrations](https://www.home-assistant.io/integrations/?search=sms&cat=notifications), [Mikrotik SMS Integration](https://github.com/jeyrb/hass_mikrotik_sms) |

Send text messages using any SMS integration that follows Home Assistant Notification model - configure which one by setting the `action` value to match, for example `action: notify.mikrotik_sms`.

Uses the `phone_number` of a [recipient](https://supernotify.rhizomatics.org.uk/latest/configuration/people/index.md), or a phone number given as a target, and cuts the message to 158 characters to fit in a single SMS.

Since SMS sends a single message with no title, by default the message and title are combined into a single string prior to cutting. Use `message_usage` in an `options` section to change the behaviour, either message only or using the title in place of the message.

Emoji and other pictographic symbols are removed, but currency signs, brackets and the like are kept. Set `simplify_text: false` in `options` to keep emoji too, though a message with emoji in it is longer than one SMS can carry, so it's sent as several, if the SMS service allows.

A `data` mapping inside the notification's `data` is passed on to the SMS integration, for example a picture for Twilio:

Example Notification with Twilio picture

```yaml
- action: supernotify.notify
  data:
    message: "Someone at the door"
    delivery:
      sms:
        data:
          data:
            media_url: https://example.com/door.jpg
```

Tip

SMS is also available without having a 4G modem by using the Home Assistant [AWS SNS Integration](https://www.home-assistant.io/integrations/aws/#sns-notify-usage/) and setting up SNS with [SMS destinations](https://docs.aws.amazon.com/sns/latest/dg/sns-mobile-phone-number-as-subscriber.html).

## Example

Example Notification

```yaml
- action: supernotify.notify
  data:
    message: "Motion detected at the front door"
    target:
        - person.house_owner
```

## Discovery

**Default delivery.** SuperNotify auto-detects the official Twilio SMS integration or the [Mikrotik SMS](https://github.com/jeyrb/hass_mikrotik_sms) HACS integration (Twilio preferred if both are present). If no `sms` delivery is defined, a `sms` delivery is generated automatically and is used for any notification with a phone number, either as a target or from a recipient's `phone_number` — same as with `email`. Any other SMS integration still needs a manually configured `action`.
