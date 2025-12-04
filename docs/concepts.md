---
tags:
  - transport
  - delivery
  - scenario
  - target
  - recipient
  - envelope
  - principles
description: Core Concepts of Supernotify for Home Assistant, including Transport, Delivery, Scenario and Recipient
---
# Core Concepts

## Transport

- *Transport* is the underlying platform that performs notifications, either out of the box from Home Assistant, or another custom component
- *Transport Adaptors* are what make the difference between regular Notify Groups and Supernotify. While a Notify Group seems to allow easy multi-channel notifications, in practice each notify transport has different `data` (and `data` inside `data`!) structures, addressing etc so in the end notifications have to be simplified to the lowest common set of attributes, like just `message`!
- Supernotify comes out the box with adaptors for common transports, like e-mail, mobile push, SMS, and Alexa, and a *Generic* transport adaptor that can be used to wrap any other Home Assistant action
- The transport adaptor allows a single notification to be sent to many platforms, even
when they all have different and mutually incompatible interfaces. They adapt notifications to the transport, pruning out attributes they can't accept, reshaping `data` structures, selecting just the appropriate targets, and allowing additional fine-tuning where its possible.
- Transport Adaptors can optionally be defined in the Supernotify config with defaults
- See [Transports](transports/index.md) for more detail

## Delivery

- A **Delivery** defines each notification channel you want to use
- While Supernotify comes with many transports, only the ones you define with a Delivery will
get used to send notifications, with the exception of *Notify Entity* transport which is
always on unless switched off.
- Deliveries allow lots of fine tuning and defaults to be made, and you can also have multiple
deliveries for a single transport, for example a `plain_email` and `html_email` deliveries.
- See [Deliveries](configuration/deliveries.md) and [Recipes](recipes/index.md) for more detail

## Scenario
- An easy way to package up common chunks of config, optionally combined with conditional logic
- Scenarios can be manually selected, in an `apply_scenarios` value of notification `data` block,
or automatically selected using a standard Home Assistant `condition` block.
- They make it easy to apply overrides in one place to many different deliveries or notifications,
and are the key to making notification calls in your automations radically simpler
- See [Scenarios](scenarios.md) and [Recipes](recipes/index.md) for more detail


## Target
- The target of a notification.
- This could be a *direct* target, like an `entity_id`, `device_id`,
e-mail address, phone number, or some custom ID for a specialist transport like Telegram or API calls.
- It also has some support, more to come, for *indirect* targets. The primary one is `person_id`,
although some other Home Assistant ones will be supported in future, like `label_id`,`floor_id`
and `area_id`.
- There's also the in-between type, *group*, which is sort of both indirect and direct. Supernotify
    will exploded these for the *Chime* integration, but otherwise ignore them.

## Recipient
- Define a person, with optional e-mail address, phone number, mobile devices or custom targets.
- This lets you target notifications to people in notifications, and each transport will pick the type
of target it wants, for example the SMS one picking phone number and the SMTP one an e-mail address
- See [People](configuration/people.md) and [Recipes](recipes/index.md) for more detail

## Envelope
- A notification customized for a specific delivery
    - List of targets filtered, for example, only e-mail addresses for SMTP integration
    - Indirect targets, like `person.xxx` are materialized into e-mail addresses, phone numbers etc
    - The `data` section of the notification may also have been customized, by the delivery definition, or application of a scenario.
- *Envelope* isn't present in the configuration - aside from the code, its only
visible when viewing an [archived notification](configuration/archiving.md), where a list of *delivered* and *undelivered* envelopes is kept.

!!! info
    For the technically minded, there's a [Class Diagram](developer/class_diagram.md) of the core classes matching these concepts.

# Core Principles

1. All a notification needs is a message, everything else can be defaulted, including all the targets
2. If you define something in an action call, it takes precedence over the defaults
   - This can be tuned by things like `target_usage`
   - The people registry is only used to generate targets if no targets given
3. Action > Scenario > Delivery > Transport for configuration and defaults
4. As unfussy as possible about how it is configured and called
   - Targets can be structured into sub-categories, or a bit list of entity ids, device ids, emails and phone numbers
   - Action `data` options like `delivery` can be a single value, list or dictionary mapping
