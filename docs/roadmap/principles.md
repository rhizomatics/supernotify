## Principles

1. There is no configuration unless configuration is necessary.

    If configuration can be reliably inferred, borrowed or defaulted then it should do so.

2. A do-nothing UI only configured integration should do something.

    If Home Assistant already configured for SMTP, or Mobile Apps configured, then by default an integration that has had zero options defined, and a notification that only has a `message` can do something sensible.

3. Keep the power of flexible configuration but don't let it get in the way

    Nobody needs to know about Delivery, Scenario or Transport until it solves a problem they have, or they like a Recipe that needs them.

4. Transports come in different categories, make those obvious and consistent

    a. Targets

    Some transports have unambiguous targets, like a phone number or email address, or a target that can could easily be made unambiguous, for example with a domain prefix, like `discord:123456789012345678`

    Other transports have no targets, like Persistent.

    Some transports have targets that are relatively fixed, like Alexa devices, while others are in theory unbounded, like email.

    Some transports have targets that are personal, like email or SMS, and others tied to a location, like a chime.

    Sometimes multiple transports can handle the same targets, like Alexa Media Player, TTS, Chime, Alexa Devices

    b. Configuration

    Some transports have everything needed configured in their own Home Assistant integration, other than perhaps which target to pick

    Chime and Generic are the extreme examples where they only make sense when explicitly configured within supernotify (although in theory
    something like sirens could be a notification target, and combined with floor/label etc).

5. The most natural way to select deliveries is to select targets.

    Rather than select a list of configuration items, if I send to "me@house.org,+439549582331,discord:554855344" I've made my intentions clear that I want to use email, SMS and Discord.

    On the other hand, no targets defined doesn't mean a notification should go to either ALL or NONE. It probably shouldn't target a persistent notification or a siren, on the other hand if there are email addresses and mobile apps defined for people, it makes sense to select them.

6. Home Assistant's native notifications, and custom add-ons, remain unsatisfactory

    There are many ways of doing the same thing, `notify.platform`,`notfiy.send_message`,`notify.mobile_app_my_old_macbook`,`assist_satellite.announce`,`alexa_devices.send_sound` etc, sometimes a dedicated action per target, sometimes a generic action, sometimes to an entity, sometimes to a device.

    Notify Entities regularize the interface but have very limited functionality, and the purist implementation means all email addresses must be pre-registered in config before use. (Some recognition of external entities with unambiguous name formats is overdue).

    v2.0.0 of Supernotify has started pulling away from the 'legacy' notification platform, with separate config, and a much easier to use notification automation UI.

7. Align with Home Assistant architecture and standards

    Make Supernotify more accessible to more users, including non-technical ones who will never use YAML. Supernotify should itself make HomeAssistant more accessible, for example by simplifying mobile push setup.

    Move towards Platinum quality scale level and maintain this quality

    Note the tension with Principle #6

8. Align with a likely vision of the future home automation

    AI will be increasingly used to drive automation, from advanced users using it for YAML to others who won't even touch ConfigFlow UI. Documentation on concepts and configuration will have agents as the primary audience.

    E-mail and SMS use are declining. Only 2% of known HA installs have the SMTP integration, SMS is much more marginal than that.

9. Don't lose intent

    If a user has marked a delivery `enabled: false` then don't confuse this in config or run time with a delivery that has incomplete configuration or not selected.

10. Entia non sunt multiplicanda praeter necessitatem.

    Minimize unnecessary concepts in config, and Home Assistant entities/devices/helpers.
