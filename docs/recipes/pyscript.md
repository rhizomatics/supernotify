---
tags:
  - recipe
  - pyscript
  - camera
  - mobile_actions
  - events
title: Send Notifications from Pyscript
description: Call Supernotify from the Pyscript integration for Home Assistant, with responses, dry runs, events and IDE autocompletion
---
# Recipe - Pyscript

## Purpose

Call Supernotify from [Pyscript](https://hacs-pyscript.readthedocs.io/) python code, check what was delivered, react to notification and mobile action events, and get autocompletion for the `supernotify` actions in an IDE.

## Implementation

Pyscript exposes every Home Assistant action as a python function, so `supernotify.notify` is called directly with the same fields as the [notify action](../usage/notifying.md). All the fields are plain keyword arguments, however they are grouped in the *Developer Tools* form.

## Example Code

### Send a notification

```python
@state_trigger("binary_sensor.driveway_detector == 'on'")
def driveway_alert():
    supernotify.notify(
        title="Driveway",
        message="Vehicle detected on the driveway",
        priority="high",
        apply_scenarios=["cctv", "driveway"],
        camera_entity_id="camera.driveway",
        media={"camera_ptz_preset": "driveway_entrance"},
        actions=[{"action_url_title": "Go to Camera", "action_url": "http://10.4.6.43/cameras/driveway/view"}],
    )
```

### Check the outcome

Add `return_response=True` to get the notification back as a dictionary, including which
deliveries were made. With `dry_run="simulate"` nothing is sent, so a script can be tried out safely.

```python
@service
def test_driveway_alert():
    result = supernotify.notify(
        message="Vehicle detected on the driveway",
        delivery=["mobile_push", "alexa_announce"],
        dry_run="simulate",
        return_response=True,
    )
    log.info(f"Supernotify outcome: {result['outcome']}")
```

The `enquire_*` actions, such as `supernotify.enquire_last_notification` or
`supernotify.enquire_active_scenarios`, only work with `return_response=True`.

### React to notifications

A `supernotify_notification` event is fired for each notification sent, with `notification_id`,
`summary`, `outcome` and `deliveries`.

```python
@event_trigger("supernotify_notification", "outcome != 'SUCCESS'")
def notification_problem(notification_id=None, summary=None, outcome=None, **kwargs):
    log.warning(f"Notification {notification_id} ({summary}) ended as {outcome}")
```

### Handle mobile actions

[Mobile actions](../usage/mobile_actions.md) arrive as the usual Home Assistant
`mobile_app_notification_action` event.

```python
@event_trigger("mobile_app_notification_action", "action == 'OPEN_GATE'")
def open_gate(**kwargs):
    cover.open_cover(entity_id="cover.driveway_gate")
```

## IDE Autocompletion

Pyscript can generate [IDE helper stubs](https://hacs-pyscript.readthedocs.io/en/stable/reference.html#ide-helpers)
for all the actions in an installation, including Supernotify's. Run the `pyscript.generate_stubs`
action, point the IDE at `<config>/pyscript/modules`, and import the stub at the top of a script:

```python
from stubs.pyscript_generated import supernotify
```

Pyscript ignores this import at runtime. The names of the deliveries configured are
included in the stub, so run `pyscript.generate_stubs` again after changing them.

!!! note
    Pyscript 2.1.0 only recognises its own two section names, so the Supernotify fields grouped under
    *Multimedia*, *Scenarios* and *Advanced* are missing from the stub and the IDE will report
    them as unknown arguments, and fields taking a list are shown as taking a single value.
    They all work when the script runs. A fix for this has been [proposed to Pyscript](https://github.com/custom-components/pyscript/pull/878).

### Typed helpers

The stub can only describe `media`, `delivery_control`, `actions`, `data` and the responses as `Any`,
since Home Assistant actions don't publish the shape of object fields. A typed python helper module
for Pyscript, with definitions for these, could be provided if there is interest - ask for it with a feature request
on [GitHub Discussions](https://github.com/rhizomatics/supernotify/discussions).
