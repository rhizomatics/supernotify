---
title: Troubleshooting
tags:
- troubleshooting
- debug
- support
- problems
description: Tips, tricks and tools for debugging issues
---
# Troubleshooting

## Options

- [AI Agents](./ai_help.md) can give very good help these days, even the free one built into [Google Search](./ai_help.md#google-and-ai-assisted-help).
- [Troubleshooting your configuration](https://www.home-assistant.io/docs/configuration/troubleshooting/) has the generic Home Assistant advice
- Use the [Archive](../configuration/archiving.md) to browse the existing notification
  - Easiest way to do this is using the [Studio Code Server](https://github.com/hassio-addons/app-vscode) app for Home Assistant
  - Switch on debug mode to get much more detailed archives,
    - `debug: true` can be added to a notification `data` section, or onto any `delivery` config
- Supernotify has a [Diagnostics](https://www.home-assistant.io/integrations/diagnostics/) bundle available from the integration page
- Have a look at the [What's New](https://supernotify.rhizomatics.org.uk/latest/changelog/), including any breaking changes, and any of the known [Issues](https://github.com/rhizomatics/supernotify/issues) or [Support Discussions](https://github.com/rhizomatics/supernotify/discussions).
- Use the [Tools](https://www.home-assistant.io/docs/tools/dev-tools/) to call the action directly, listen to events, or view states
  - Since Supernotify manages Home Assistant contexts, you can see the entire history of a why a notification happened, what the original trigger was, and also downstream things like moving and zooming a camera, all laid out in the state history
  - Supernotify also has lots of additional [actions](../usage/actions.md) to enquire about the internals, and offers lots of diagnostic entities
- The [Debugging a Transport Integration](../recipes/debug_integration.md) has an example of working through issues with one of the underlying notification transports

## Advanced Agent Usage
- If you have a desktop or coding agent, then giving it access to Home Assistant config make it much easier to resolve issues and correct config.
  - Easiest way of doing that is with the [Samba Share](https://github.com/home-assistant/addons/tree/master/samba) app for Home Assistant.
  - For example, on a Mac you can have the local `/Volumes/config` reading the main `\config` directory of Home Assistant.
  - Caution is due where passwords and other secrets inside the Home Assistant directory could be exposed.
- The [Assist](../usage/assist.md) integration also supports [MCP](https://www.home-assistant.io/integrations/mcp/) for queries
- For more advanced usage, the [Home Assistant REPL](../developer/ha_repl.md) developer shell can give easy agent access to the APIs, or deep access direct into the live internals and database with `live` mode. The latter is the sharpest tool available for agents.
