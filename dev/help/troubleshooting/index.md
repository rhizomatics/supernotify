# Troubleshooting

Source: https://supernotify.rhizomatics.org.uk/latest/help/troubleshooting/

## Common Problems

### A notification doesn't arrive

**Symptom**: the notification is sent, without an error, but nothing arrives, or it doesn't arrive by every delivery expected. The log has a warning like `SUPERNOTIFY No deliveries made for ...`, followed by the reasons.

**Cause**: a rule left it out, as configured. The reasons are:

| Reason               | Why                                                       | To fix                                                                                                                                                     |
| -------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SNOOZED`            | The recipient, delivery or everything is snoozed          | List snoozes with `supernotify.enquire_snoozes`, and end them with `supernotify.unsnooze`                                                                  |
| `PRIORITY`           | The notification's priority isn't one the delivery is for | Change the notification's `priority`, or the delivery's, see [Deliveries](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/index.md) |
| `OCCUPANCY`          | The delivery is only for recipients at home, or only away | Check with `supernotify.enquire_occupancy`, see [Deliveries](https://supernotify.rhizomatics.org.uk/latest/configuration/deliveries/index.md)              |
| `DELIVERY_CONDITION` | The delivery's conditions don't hold                      | See [Conditions](https://supernotify.rhizomatics.org.uk/latest/configuration/conditions/index.md)                                                          |
| `NO_SCENARIO`        | The delivery is only for a scenario that doesn't apply    | Check with `supernotify.enquire_active_scenarios`, see [Scenarios](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/index.md)         |
| `TRANSPORT_DISABLED` | The transport is switched off                             | Switch it on, or press *Reset overrides*, see [Entities](https://supernotify.rhizomatics.org.uk/latest/usage/entities/index.md)                            |
| `NO_TARGET`          | The delivery has no one to send to                        | Give the recipients the addresses or devices it needs, see [People](https://supernotify.rhizomatics.org.uk/latest/configuration/people/index.md)           |

`supernotify.enquire_last_notification` shows what happened to the last notification, and the [Archive](https://supernotify.rhizomatics.org.uk/latest/configuration/archiving/index.md) to every one.

### An action says Supernotify isn't loaded

**Symptom**: a `supernotify.*` action, such as `supernotify.notify`, fails with *Supernotify isn't loaded*.

**Cause**: Supernotify is still starting, failed to start, or is disabled. If it failed, the log has *Supernotify failed to start, and will retry*, with the reason, and it tries again by itself.

**Fix**: check the reason in the log and on the integration's page, correct the configuration, and reload the integration, or enable it if it's disabled.

### The same notification is only sent once

**Symptom**: a notification sent again soon after, with the same message and title, doesn't arrive.

**Cause**: duplicate detection, which leaves out a repeat of a recent notification at the same or a lower priority.

**Fix**: send it with `force_resend: true`, or change the policy, see [Duplicate Detection](https://supernotify.rhizomatics.org.uk/latest/configuration/dupe_detection/index.md).

### No emails are sent

**Symptom**: nothing goes by email, and the log has a warning at startup that there is no sender.

**Cause**: a direct SMTP email needs a sender address, as Home Assistant's own SMTP integration does.

**Fix**: set `sender` in the email transport's `options`, or set up the SMTP integration from the UI, for Supernotify to reuse, see [Email](https://supernotify.rhizomatics.org.uk/latest/transports/email/#configuring).

### An image is missing from an email

**Symptom**: the email arrives without its image, and the log has a warning that the attachment was skipped.

**Cause**: only files in Supernotify's media path, or a folder Home Assistant allows files to be read from, are attached.

**Fix**: save the image in the media path, `www`, a folder in `media_dirs` or one in `allowlist_external_dirs`, see [Email](https://supernotify.rhizomatics.org.uk/latest/transports/email/#image-attachments).

### A snapshot URL gives no image

**Symptom**: a notification with a `snapshot_url` arrives without the image, and there may be a repair listing why.

**Cause**: the URL didn't give an image, it was bigger than the *Largest Snapshot Download* setting, or, with *Only Local Snapshot URLs* on, it isn't Home Assistant itself, on the same network, or in `allowlist_external_urls`.

**Fix**: see [Snapshot URLs](https://supernotify.rhizomatics.org.uk/latest/configuration/multimedia/#snapshot-urls).

### A template shows as text

**Symptom**: a message has `{{ ... }}` in it, rather than what the template should give.

**Cause**: the *Render Templates in Notify Calls* setting is off, as it is for new installs, so a template that reaches Supernotify unrendered, such as from AppDaemon or a `{% raw %}` block, is left as it is.

**Fix**: switch the setting on, or move the template into a scenario's `message_template`, see [Automation and Templates](https://supernotify.rhizomatics.org.uk/latest/usage/notifying/#automation-and-templates).

### A scenario's binary sensor is unknown

**Symptom**: a *Scenario Condition* binary sensor stays *unknown*.

**Cause**: `refresh` is off in `scenario_control`, so nothing keeps its state current, or the scenario has no conditions.

**Fix**: switch on `refresh`, see [Entities](https://supernotify.rhizomatics.org.uk/latest/usage/entities/#how-entities-update) and [Scenarios](https://supernotify.rhizomatics.org.uk/latest/configuration/scenarios/index.md).

## Options

- [AI Agents](https://supernotify.rhizomatics.org.uk/latest/help/ai_help/index.md) can give very good help these days, even the free one built into [Google Search](https://supernotify.rhizomatics.org.uk/latest/help/ai_help/#google-and-ai-assisted-help).
- [Troubleshooting your configuration](https://www.home-assistant.io/docs/configuration/troubleshooting/) has the generic Home Assistant advice
- Use the [Archive](https://supernotify.rhizomatics.org.uk/latest/configuration/archiving/index.md) to browse the existing notification
- Easiest way to do this is using the [Studio Code Server](https://github.com/hassio-addons/app-vscode) app for Home Assistant
- Switch on debug mode to get much more detailed archives,
  - `debug: true` can be added to a notification `data` section, or onto any `delivery` config
- Supernotify has a [Diagnostics](https://www.home-assistant.io/integrations/diagnostics/) bundle available from the integration page
- Have a look at the [What's New](https://supernotify.rhizomatics.org.uk/latest/changelog/), including any breaking changes, and any of the known [Issues](https://github.com/rhizomatics/supernotify/issues) or [Support Discussions](https://github.com/rhizomatics/supernotify/discussions).
- Use the [Tools](https://www.home-assistant.io/docs/tools/dev-tools/) to call the action directly, listen to events, or view states
- Since Supernotify manages Home Assistant contexts, you can see the entire history of a why a notification happened, what the original trigger was, and also downstream things like moving and zooming a camera, all laid out in the state history
- Supernotify also has lots of additional [actions](https://supernotify.rhizomatics.org.uk/latest/usage/actions/index.md) to enquire about the internals, and offers lots of diagnostic entities
- The [Debugging a Transport Integration](https://supernotify.rhizomatics.org.uk/latest/recipes/debug_integration/index.md) has an example of working through issues with one of the underlying notification transports

## Advanced Agent Usage

- If you have a desktop or coding agent, then giving it access to Home Assistant config make it much easier to resolve issues and correct config.
- Easiest way of doing that is with the [Samba Share](https://github.com/home-assistant/addons/tree/master/samba) app for Home Assistant.
- For example, on a Mac you can have the local `/Volumes/config` reading the main `\config` directory of Home Assistant.
- Caution is due where passwords and other secrets inside the Home Assistant directory could be exposed.
- The [Assist](https://supernotify.rhizomatics.org.uk/latest/usage/assist/index.md) integration also supports [MCP](https://www.home-assistant.io/integrations/mcp/) for queries
- For more advanced usage, the [Home Assistant REPL](https://supernotify.rhizomatics.org.uk/latest/developer/ha_repl/index.md) developer shell can give easy agent access to the APIs, or deep access direct into the live internals and database with `live` mode. The latter is the sharpest tool available for agents.
