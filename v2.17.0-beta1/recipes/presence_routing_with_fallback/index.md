# Recipe - Notify Whoever's Home, Fall Back to Everyone

Source: https://supernotify.rhizomatics.org.uk/latest/recipes/presence_routing_with_fallback/

## Purpose

Send a notification only to the people currently home, each on their own device(s) - and if nobody's home, send it to everyone instead, so it still reaches someone. Make the config as easy as possible, don't make list everybody and their devices every time.

## Implementation

Two Deliveries, both automatically getting their lists of targets the normal way from known recipients (either automatically discovered from Home Assistant and/or manually defined). This means not needing to either name a person or a device, so this scales to any number of recipients with no further config:

- `occupancy: only_in`
- narrows the recipient list down to just whoever's home. Unlike `any_in` (which is true if anyone's home, but still resolves to everyone), `only_in` genuinely narrows *which* recipients the delivery reaches - see [Delivery Inclusion](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/#delivery-inclusion).
- `occupancy: all_out`
- Does the same the other way round - it resolves to everyone, but only when every recipient is away.

Note that `inclusion: fallback` plays no part in this - see the warning below.

## Example Configuration

```yaml
supernotify:
  recipients:
    - person: person.alex
    - person: person.sam
  delivery:
    notify_home:
      transport: mobile_push
      inclusion:
        - scenario
      occupancy: only_in
    notify_everyone:
      transport: mobile_push
      inclusion:
        - scenario
      occupancy: all_out
  scenarios:
    presence_routed:
      alias: "Notify whoever's home"
      delivery:
        notify_home:
        notify_everyone:
```

Add a third recipient and both deliveries pick it up automatically - nothing else changes.

## Variations

### One specific device per person, not all of them

`occupancy: only_in` narrows *which recipients* a delivery reaches, not which of a person's own registered devices get notified - if someone has two phones, both get the notification. To pin a delivery to one named device per person instead, drop the shared `notify_home` delivery and give each person their own, with `target_usage: fixed` and a bare `mobile_app_id` target (see [Explicit Targets](https://supernotify.rhizomatics.org.uk/latest/transports/mobile_push/#explicit-targets)):

```yaml
  delivery:
    notify_alex:
      transport: mobile_push
      inclusion:
        - scenario
      target_usage: fixed
      target:
        - mobile_app_alex_primary
      conditions:
        condition: state
        entity_id: person.alex
        state: home
```

This doesn't scale the way the `occupancy`-only version does - a new recipient needs their own delivery block - but it's the only way to express "this one device, not that one".

`inclusion: fallback` would do nothing here - don't add it

It's tempting to also add `fallback` to `notify_everyone`'s `inclusion`, since that's its role. Don't - it would be dead weight. `fallback` only wires a delivery into a separate mechanism that fires when *nothing at all* delivered for the whole notification, and only adds a delivery that isn't *already* selected some other way. `notify_everyone` is already named directly in the scenario's own `delivery:` map, so it's always selected via plain `scenario` inclusion - the `fallback` mechanism never gets a chance to act, since there's nothing left for it to add. All the actual gating here is `occupancy: all_out`; strip that out while keeping `inclusion: fallback` and the delivery would fire on *every* notification, not just when nobody's home - naming a delivery directly always selects it, regardless of any `fallback` flag. See [Delivery Inclusion](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/#delivery-inclusion) for the full explanation.
