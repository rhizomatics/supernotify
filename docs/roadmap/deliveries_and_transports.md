# Deliveries and Transports

See also [Principles](./principles.md).

## Context

This is a typical trade-off between ease of use and flexibility.

For convenience, Transports should be as automated as possible and Deliveries only a thing for advanced users  - in my notification, if I want to deliver to email, mobile push and Ntfy then all I should have to do is list the names of those transports, simple names like `email`,`mobile_push` and `ntft`.

Delivery was the original configuration object, Transport only got delivery config to centralize common config across multiple Deliveries, yet Transport is the 'obvious' object, and the only one necessary.

Over time, autoconfigure of 'DEFAULT_xxxx' deliveries has closed some of that gap, so for example a purely UI configured Supernotify can easily send out notifications to mobile push and email. 2.5.0 beta added more, however this feels like coping with an underlying issue rather than making the necessary simplifications. The 1:M delivery:transport relationship which is very flexible but a barrier for newcomers or less technical, especially when there's no ConfigFlow for Delivery yet.

## Design Decisions

1. Every Transport is also a Delivery if it can be auto-configured, with the same name.

    This implies merging back the extensions of `DELIVERY_SCHEMA` back into `DELIVERY_CONFIG_SCHEMA`

2. Nobody needs a Delivery unless they need more than 1 pre-set config for the same transport

    Do everything possible on the Transport level, so no reason to create Delivery until 2 flavours needed, like a low priority and high prioroty, or occupied and unoccupied.

    Transport is still simpler than Scenario, so maximize what can be done with just Transport

3. Transports with unambiguous targets are selected by default, and the target list makes the decision of which deliveries to use.

    Exception to this is Mobile Push, where zero targets and zero explicit deliveries implies 'push this to all the mobile apps'

    The scope of this can be extended by use of qualified targets, e.g. `discord:5893434344` as an option

4. Transports with ambiguous or no targets can be explicitly selected by name but aren't included by default

5. Transports that cannot be auto-configured are ignored unless explicitly configured at Transport or Delivery level

    No `binary_sensor` or similar entity created for transports which have a module supplied with Supernotify but never used in the home

    This also implies that each Transport knows its minimum viable configuration

6. Delivery selection in notification only needed in notification to switch off implicit or switch on explicit

    Otherwise everything left up to target selection. Limiting deliveries useful where there's auto discovered mobile devices, or emails / SMS numbers provided for Recipients.

7. A little repetition is more tolerable than understanding an individual integrations unique abstractions

    Most of the transports would be usable with zero YAML, albeit there might be some more repetitive data elements, like telegram/slack IDs that could be simplified into a Delivery object, though for some people repetition simpler than abstract concepts, and learning YAML and Studio Code Server

8. Switch entities continue as they are with delivery and transport

    `switch.transport_email` switches off all email deliveries, including the default
    `switch.delivery_email` switches off only the default delivery.
    For most people, these will equivalent, if they have 0 or 1 explicitly configured deliveries

    The enabled/disabled state should in future persist across restarts.

    Don't generate switches for transports that can't be used, e.g. Telegram if there's no Telegram integration in the home

9. Backward compatibility for original `DEFAULT_email` style

    If there's no delivery called `DEFAULT_email` then notification handling will try `email`
    This won't extend to re-creating binary sensors or other diagnostic artefacts under those names

10. Transport Specific

    TTS - Only make this transport available if there is a suitable service available and at least one media_player defined
    Media Player - autogen delivery needs explicit selection
    HACS integrations, e.g. Alexa Media Player - detect these using find_service
    Alexa Devices - make the autogen delivery default disabled if there's an Alexa Media Player transport available so there's not double notification to same devices
    Chime/Generic - everything possible can be defined under transport without creating an Delivery config item. `chime_aliases` needs to be defined for an autogen Delivery otherwise treated like unconfigured integration. Similar for generic without action defined.

11. Default vs Explicit

This is partly a judgement call - email and mobile push are the 'obvious' ways to deliver notification, and partly about revealed intention in config - which was the original rationale for making Delivery inclusion `default` by default.

This also intersects with target generation, and conditional deliveries.

One idea is making delivery `inclusion` a mandatory field, since its a minefield for defaulting.

Reasons to make a Delivery included in selection by default:

1. Its "obvious" - really only mobile push or e-mail
2. There are already conditions applied to Delivery - priority, occupancy or condition. These imply that the delivery inclusion is default, since otherwise the conditions would never be tested.
3. Delivery will only happen if a matching target is unambiguously provided, AND the delivery does not generate its own targets.

On the other hand, if a delivery is explicitly configured, and given no targets, it is reasonable to auto generate a target list, since it was implied.

The worst case for a new user is that a notification gets over-delivered, including every voice assistant in the house reading out a long message, or mobile charges unexpectedly rung up sending SMS.


One solution is making delivery `inclusion` a mandatory field, since its a minefield for defaulting.

## Future Changes

1. Storage of switch enable/disable, so choices persist across restarts
2. Domain qualified targets, e.g. media:media_player.kitchen, tts:media_player.kitchen, discord:8943493434
3. Enable `mobile_push` if mobile apps / users defined in Home Assistant (this is dynamic config, so doesn't have a restart associated with it ) and also update any recipient and device config
4. Alexa Devices should pre-populate with all the `announce` devices if no target given, and be an explicit inclusion for delivery. This is in-line with being maximally useful for minimal UI only config

### Target Driven Selection

There are categories and sub-categories of target that could be used to better automate selection

- Simple - an e-mail address. If multiple integrations support e-mail, top priority one wins
- Complicated - Notify Entity - multiple things handle these, including the bare bones Notify Entity service plus things like html5 that work around its limitations. In effect there are sub-classes of Notify Entity that are tricky to identify
- None - persistent has no target, generic could have anything

The same target could also be used for different things, such as a media player used for both chime and announcement.

One step up is notifying a Person, and doing that in some order - for example, send each Recipient exactly one notification, in the first working form for them.

Target types differ also in being completely ephemeral - a chime, partially ephmeral like a mobile notification, or persistent, like an e-mail, SMS or indeed Persistent Message.

Use cases could be:

- Send an announcement preceded by a chime
- Send everyone their preferred persistent message and preferred push alert
- Its critical, so contact someone by any means possible


## Example

```yaml:
- action: supernotify.notify
    data:
        title: Multi modal notification
        message: Sending to email, SMS, telegram and however Billy is configured
        target:
         - johnny@43acacia.avenue.com
         - +4304283883222
         - person.billy_mctest
         - telegram: 123456789
```

```yaml:
- action: supernotify.notify
    data:
        title: Email notification
        message: Sending to parents, email only
        target:
         - person.billy_mctest
         - person.sally_mctest
        delivery: email
```
