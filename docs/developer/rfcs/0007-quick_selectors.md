# RFC 0007: Quick Selectors

2026-10-06 · Jey Burrows · Status: draft

## Summary

Current design goals are to increase scope of UI, and give as much capability as possible to people who aren't technical, won't mess with YAML, and probably not with conditions.

Looking at my own use of scenarios, the biggest single thing that would cut down the number I have is filtering deliveries by priority and armed state. That covers being quiet at night, or doing something different when house is unoccupied.

## Quick Selectors

A combination of priority and armed state, which makes a simple alternative both to AND/OR login in conditions, and to the need for scenarios.

They combine the priority - Minimal, Low, Medium, High, Critical and a special *Any* - with the main armed states - `DISARMED`, `ARMED_AWAY`, `ARMED_HOME`, `ARMED_NIGHT` and a special `ARMED_ANY`.

They are intentionally simplistic, no regular expressions, no conditional logic (although a list of them is effectively a set of ORed AND conditions ).

This also means the general integration settings needs a way of selecting which alarm control panel, though as most people have 0..1 panels, it can automatically choose the first and allow that to be overridden. Most to benefit are **Auto Arm** users, where the `ARMED_HOME`, `ARMED_AWAY` is automatically set based on occupancy.

### Example Selectors

```yaml
- LOW_PRIORITY_DISARMED
- CRITICAL_PRIORITY_ARMED_ANY
- ANY_PRIORITY_ARMED_AWAY
```

Example below is in YAML, however the primary target would be the new Delivery Configflow UI, which then makes them more widely accessible.

### Example Delivery YAML

```yaml
delivery:
    siren:
       select:
          - CRITICAL_PRIORITY_ARMED_ANY
          - CRITICAL_PRIORITY_DISARMED
          ...
     alexa_devices:
        deselect:
           - ANY_PRIORITY_ARMED_AWAY
           - MINIMAL_PRIORITY_ARMED_ANY
           - MINIMAL_PRIORITY_DISARMED
 ```

### Questions and Issues

Why not `occupancy`?
  Its only simple if combinations limited, and occupancy is accounted for by alarm control panels (`ARMED_HOME`,`DISARMED`,`ARMED_NIGHT`)
Why not time of day?
  `ARMED_NIGHT` covers some of that, although there are bigger gaps - 1) day/night during `ARMED_AWAY` or `ARMED_VACATION` and 2) night-time vs bed-time, such as switch on floodlights if its dark but only squelch announcements when its bedtime (it can be dark at 4pm in Scottish winter and bright daylight at 4am in summer)
