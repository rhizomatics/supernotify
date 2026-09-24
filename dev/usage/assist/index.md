# Assist and AI Agents

Beta

This is a first beta, and feedback is very welcome on [GitHub issues](https://github.com/rhizomatics/supernotify/issues), especially on how well your conversation agent picks the right tool and fills it in.

Supernotify can give tools to [Assist](https://www.home-assistant.io/voice_control/), so an AI conversation agent can send notifications, snooze them, and explain what happened to them. It works by voice or from the chat icon in the app.

The same tools are offered to AI agents connected through Home Assistant's [Model Context Protocol Server](https://www.home-assistant.io/integrations/mcp_server/), as long as the server exposes the Assist API.

## Switching On

Nothing is offered until you switch it on. In **Settings** > **Devices & services** > **Supernotify** > **Configure**, choose **LLM Tools (beta)**. There are two switches:

| Switch           | Tools                                                                     |
| ---------------- | ------------------------------------------------------------------------- |
| Action tools     | Send notifications, and snooze or silence them                            |
| Diagnostic tools | Recent notifications, dry runs, current snoozes, and documentation lookup |

Needs an AI conversation agent

The tools are only used by a conversation agent that runs an AI model, such as OpenAI, Anthropic, Google Gemini or Ollama. Home Assistant's own built-in agent matches fixed sentences and can't use them. If Assist answers "Sorry, I couldn't understand that", or "I am not aware of any device called…", the built-in agent is answering.

1. Add an AI conversation integration, and in its options set **Control Home Assistant** to **Assist**.
1. In **Settings** > **Voice assistants**, choose that conversation agent for the assistant you talk or chat to.

The tools also need a recent Home Assistant. They don't appear on 2026.2 or earlier.

## What You Can Ask

| Tool                                | Ask things like                                       |
| ----------------------------------- | ----------------------------------------------------- |
| `supernotify__notify`               | "Tell everyone dinner is ready"                       |
| `supernotify__snooze`               | "Mute the doorbell camera alerts for an hour"         |
| `supernotify__recent_notifications` | "Why didn't I get the washing machine alert?"         |
| `supernotify__dry_run`              | "If the smoke alarm goes off, who gets told and how?" |
| `supernotify__snoozes`              | "What notifications have I snoozed?"                  |
| `supernotify__help`                 | "How do I e-mail a camera snapshot with Supernotify?" |

Ask in your own words - there's no need to name the tools.

The agent is told the names of your deliveries, scenarios and recipients, including any `alias`, so it can match "the family chat" to a delivery. Good aliases help it choose well.

### Sending

The agent can give a message, title and priority, pick recipients by name, and choose deliveries and scenarios. If it doesn't choose deliveries, Supernotify picks them as it would for an automation, from the priority, scenarios and who is home. Any priority can be used, including `critical`.

Some fields of `supernotify.notify` are not offered, so an agent can only reach people and devices you have already configured:

- `custom_target`, since it takes any e-mail address, phone number or chat id. Send to those through [Recipients](https://supernotify.rhizomatics.org.uk/latest/configuration/people/index.md) or notify entities instead.
- `actions`, custom mobile push actions.
- Media URLs and camera snapshots.

### Snoozing

The agent can `snooze` for a number of minutes, `silence` until undone, `unsnooze` one snooze, or `clear_all` snoozes. A snooze can cover everything, non-critical notifications only, or one delivery, transport, priority or camera.

If the agent doesn't name who the snooze is for, it applies to the person asking, if Supernotify can match their Home Assistant user to a recipient. Otherwise it applies to everyone. See [Snoozing](https://supernotify.rhizomatics.org.uk/latest/usage/snoozing/index.md) for how snoozes work.

### Explaining

`supernotify__recent_notifications` lists recent notifications with, for each delivery, whether it sent, was skipped or failed, and why. It also shows what selected each delivery, and who was home at the time, since that decides some deliveries.

Turn on the file [archive](https://supernotify.rhizomatics.org.uk/latest/configuration/archiving/index.md) to get a history. Without it, only the most recent notification since Home Assistant started is known.

### Dry Run

`supernotify__dry_run` works out which deliveries a notification would use right now, and who it would reach, without sending anything. It makes the same checks as a real notification, including snoozes, priorities, conditions and who is home, except the duplicate check. E-mail addresses and phone numbers are partly masked.

### Help from the Documentation

`supernotify__help` looks up this documentation site, including the recipes and configuration examples, and gives the agent the best matching pages to answer from, with links. It fetches the documentation from `supernotify.rhizomatics.org.uk` the first time it's used, then at most once a day. The documentation is for the latest release, and in English, though the agent can answer in your language.
