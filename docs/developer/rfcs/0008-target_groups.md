# RFC 0008: Target Groups

2026-10-06 · Jey Burrows · Status: draft

## Problem

Supernotify features the ability to supply a mixed list of targets and work out what goes where. However repeated notifications might need the same mixed list of targets causing duplication and targets to be missed. There is also no easy way from Home Assistant context that expect a notify entity to use that list of targets. The group functionality in Home Assistant isn't useful since it expects and homogeneous set of entity_ids, and Supernotify may have a mix of email addresses, phone numbers, entity ID from different platforms and custom IDs.

## Solution

Add a target keyword to scenario which allows the same set of target definitions as used on an action and elsewhere. Since scenarios can also be Notify Entities,this means it becomes very easy to target that whole group from any automation, Alert, script, etc.

The complication comes if there are multiple scenarios with targets or the scenario is applied to an action and/or delivery they also have targets. To resolve that a scenario, we also have a **Target Priority**, which is a new concept introduced for this change, and the existing **Target Usage**

A target priority is a number from `1` to `100` with the default being `40` for `delivery` configurations and `60` for actions. which applies to regular actions and deliveries scenarios can be made with a priority anywhere in that range to determine which ones in a replace or merge scenario.

If two or more scenarios are ambiguous, raise a repair and suggest tuning so one has priority raised or lowered.

The target priority mechanism would be extended to all other target sources, e.g. if a delivery conflicted with an action.

### Example

In this example, notifications are restricted to the 3 targets. Other targets will get ignored because of the `fixed` and if there's another `fixed` set of targets it will get ignored if priority less than `100`.

```yaml
scenarios:
   parents_only:
      targets:
        - person.mum
        - person.dad
        - notify.dads_study_alexa_announce
       target_usage: fixed
       target_priority:  100
```

## Quandaries

- What if one thing is `target_usage: fixed` and another is `target_usage: merge_always`? What if the `merge_always` out-prioritizes the `fixed`?
  - Use case
    - bcc delivery that adds an email address to an archiving mailbox, and this is the only thing with target priority 100.
  - Need a matrix of `x` vs `y` for the design, and also for resulting docs
- There are lots of `priority` use already, so could be confusing term
