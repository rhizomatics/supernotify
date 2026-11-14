# RFC 0008: Target Groups

2026-10-06 · Jey Burrows · Status: draft

## Problem

Supernotify features the ability to supply a mixed list of targets and work out what goes where. However repeated notifications might need the same mixed list of targets causing duplication and targets to be missed. There is also no easy way from Home Assistant context that expect a notify entity to use that list of targets. The group functionality in Home Assistant isn't useful since it expects and homogeneous set of entity_ids, and Supernotify may have a mix of email addresses, phone numbers, entity ID from different platforms and custom IDs.

## Solution

Add a target keyword to scenario which allows the same set of target definitions as used on an action and elsewhere. Since scenarios can also be Notify Entities,this means it becomes very easy to target that whole group from any automation, Alert, script, etc.

The complication comes if there are multiple scenarios with targets or the scenario is applied to an action and/or delivery they also have targets. To resolve that a scenario, we also have a **Target Priority**, which is a new concept introduced for this change, and the existing **Target Usage**

A **Target Rank** is a number from `1` to `100` with the default being `40` for `delivery` configurations and `60` for action data. which applies to regular actions and deliveries scenarios can be made with a rank anywhere in that range to determine which ones in a replace or merge scenario.

If two or more scenarios are ambiguous, raise a repair and suggest tuning so one has rank raised or lowered.

The target rank mechanism would be extended to all other target sources, e.g. if a delivery conflicted with an action.

### Example

In this example, notifications are restricted to the 3 targets. Other targets will get ignored because of the `fixed` and if there's another `fixed` set of targets it will get ignored if rank less than `100`.

```yaml
scenarios:
   parents_only:
      targets:
        - person.mum
        - person.dad
        - notify.dads_study_alexa_announce
       target_usage: fixed
       target_rank:  100
```

## Quandaries

- What if one thing is `target_usage: fixed` and another is `target_usage: merge_always`?
  - Could be 2 scenarios clashing, or scenario and delivery, or scenario vs delivery vs action (service) data
  - What if the `merge_always` out-prioritizes the `fixed`?
  - Use case
    - bcc delivery that adds an email address to an archiving mailbox, and this is the only thing with target priority 100.
    - delivery has `merge_always` with max rank, which merges onto the fixed


## Reference

- `no_action` - Only uses the Delivery target if there's no target on the notification action call
- `no_delivery` - Only uses the Delivery target if there's no target applicable to this delivery
- `merge_delivery`- Combines the targets in the Delivery with any on the action call, only where delivery already has a target
- `merge_always` - Combines the targets in the Delivery with any on the action call, or if there's
  no target on the notification, it defaults to the Delivery target
- `fixed` - Only ever delivers to the targets in the Delivery config, ignoring any direct or indirect (for example `person_id`) in the action call


| Low Rank/High Rank | no_delivery | no_action | fixed       | merge_always | merge_delivery         |
| ------------------ | ----------- | --------- | ----------- | ------------ | ---------------------- |
| no_delivery        | *combine*   | *combine* | fixed(high) | *combine*    | *combine*              |
| no_action          | *combine*   | *combine* | fixed(high) | *combine*    | *combine*              |
| fixed              | fixed(low)[1]  | fixed(low)[1] | fixed(high) | *combine*    | *combine*              |
| merge_always       | *combine*   | *combine* | fixed(high) | *combine*    | *combine*              |
| merge_delivery     | *combine*   | *combine* | fixed(high) | *combine*    | *combine*              |

[1] fixed vs higher rank `no_delivery` or `no_action` is a no-op combine, i.e. there's no need for the back up no_delivery/no_action targets because targets provided by the `fixed` list
