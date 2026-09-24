---
tags:
  - assist
  - ai
  - llm
  - openai
  - gemini
  - voice
  - claude
  - mcp
  - chatgpt
  - ollama
  - chat
description: Let Home Assistant Assist, and AI agents connected through its MCP server, send, snooze and explain notifications
---
# Assist and AI Agents

!!! warning "Early Access"
    This is an initial implementation, limited to English. Feedback and help with other languages is very welcome on
    [GitHub issues](https://github.com/rhizomatics/supernotify/issues), especially on how well your
    conversation agent picks the right tool and fills it in.

Supernotify can give tools to [Assist](https://www.home-assistant.io/voice_control/), so a conversation agent can send notifications, snooze them, and explain what happened to them. It works by voice or from the chat icon in the app.

The same tools are offered to AI agents connected through Home Assistant's [Model Context Protocol Server](https://www.home-assistant.io/integrations/mcp_server/), as long as the server exposes the Assist API.

A more limited set of interactions, without the flexibility of AI understanding, is available for the basic non-AI Assist agent, using a set of fixed sentence structures, see [Built-in Agent Sentences](#built-in-agent-sentences) for more info.

!!! note "Not Just Voice"
  Even if you only ever type to the agent in a chat window, the place in Home Assistant where you manage them is called **Voice Assistants**.

## Switching On

Nothing is offered until you switch it on. In **Settings** > **Devices & services** > **Supernotify** >
**Configure**, choose **Assist and AI agents**. There are three switches:

| Switch                   | What it gives                                                             |
|--------------------------|---------------------------------------------------------------------------|
| Action tools             | Send notifications, and snooze or silence them                            |
| Diagnostic tools         | Recent notifications, dry runs, current snoozes, and documentation lookup |
| Built-in agent sentences | A few English [sentences](#built-in-agent-sentences) for the agent without AI |

!!! note "Needs an AI conversation agent"
    The tools are only used by a conversation agent that runs an AI model, such as OpenAI, Anthropic,
    Google Gemini or Ollama. Home Assistant's own built-in agent matches fixed sentences and can't use
    them. If Assist answers "Sorry, I couldn't understand that", or "I am not aware of any device
    called…", the built-in agent is answering.

    1. Add an AI conversation integration, and in its options set **Control Home Assistant** to **Assist**.
    2. In **Settings** > **Voice assistants**, choose that conversation agent for the assistant you talk or chat to.

    The tools also need a recent Home Assistant. They don't appear on 2026.2 or earlier.

    Without an AI model, switch on **Built-in agent sentences** instead, see below.

## What You Can Ask

| Tool                                | Ask things like                                              |
|-------------------------------------|--------------------------------------------------------------|
| `supernotify__notify`               | "Tell everyone dinner is ready"                              |
| `supernotify__snooze`               | "Mute the doorbell camera alerts for an hour"                |
| `supernotify__recent_notifications` | "Why didn't I get the washing machine alert?"                |
| `supernotify__dry_run`              | "If the smoke alarm goes off, who gets told and how?"        |
| `supernotify__snoozes`              | "What notifications have I snoozed?"                         |
| `supernotify__help`                 | "How do I e-mail a camera snapshot with Supernotify?"        |

Ask in your own words - there's no need to name the tools.

The agent is told the names of your deliveries, scenarios and recipients, including any `alias`, so
it can match "the family chat" to a delivery. Good aliases help it choose well.

### Sending

The agent can give a message, title and priority, pick recipients by name, and choose deliveries and
scenarios. If it doesn't choose deliveries, Supernotify picks them as it would for an automation, from
the priority, scenarios and who is home. Any priority can be used, including `critical`.

Some fields of `supernotify.notify` are not offered, so an agent can only reach people and devices
you have already configured:

- `custom_target`, since it takes any e-mail address, phone number or chat id. Send to those through
  [Recipients](../configuration/people.md) or notify entities instead.
- `actions`, custom mobile push actions.
- Media URLs and camera snapshots.

### Snoozing

The agent can `snooze` for a number of minutes, `silence` until undone, `unsnooze` one snooze, or
`clear_all` snoozes. A snooze can cover everything, non-critical notifications only, or one delivery,
transport, priority or camera.

If the agent doesn't name who the snooze is for, it applies to the person asking, if Supernotify can
match their Home Assistant user to a recipient. Otherwise it applies to everyone. See
[Snoozing](snoozing.md) for how snoozes work.

### Explaining

`supernotify__recent_notifications` lists recent notifications with, for each delivery, whether it
sent, was skipped or failed, and why. It also shows what selected each delivery, and who was home at
the time, since that decides some deliveries.

Turn on the file [archive](../configuration/archiving.md) to get a history. Without it, only the most
recent notification since Home Assistant started is known.

### Dry Run

`supernotify__dry_run` works out which deliveries a notification would use right now, and who it
would reach, without sending anything. It makes the same checks as a real notification, including
snoozes, priorities, conditions and who is home, except the duplicate check. E-mail addresses and
phone numbers are partly masked.

### Help from the Documentation

`supernotify__help` looks up this documentation site, including the recipes and configuration examples, and gives the agent the best matching pages to answer from, with links. It fetches the
documentation from `supernotify.rhizomatics.org.uk` the first time it's used, then at most once a day. The documentation is for the latest release, and in English, though the agent can answer in your language.

### Tuning the Agent Character

Additional prompts to use before conversations can be set in the *Voice Assistants* configuration, see [Creating a Voice Assistant Personality](https://www.home-assistant.io/voice_control/assist_create_open_ai_personality/#creating-a-voice-assistant-personalitywith-an-llm-based-conversation-agent).

## Built-in Agent Sentences

Home Assistant's built-in [Conversation](https://www.home-assistant.io/integrations/conversation) agent doesn't use an AI model, so it can't use the tools above, but it can understand fixed sentences. Switch on **Built-in agent sentences** and it understands these, by voice or in the chat:

| Say                                                      | Does                                          |
|----------------------------------------------------------|-----------------------------------------------|
| "Tell *Alice* that *dinner is ready*"                    | Notifies a recipient, by name or alias        |
| "Send a message to *everyone* saying *leaving now*"      | Notifies everyone, as an automation would     |
| "Snooze my notifications for *30* minutes"               | Snoozes everything                            |
| "Mute all notifications for an hour"                     | Snoozes everything for an hour                |
| "Snooze notifications until *15:30*"                     | Snoozes everything until then, today or tomorrow |
| "Silence notifications"                                  | Silences everything until turned back on      |
| "Turn my notifications back on"                          | Undoes the snooze or silence                  |
| "What was the last notification"                         | Says what it was, and what sent it            |

Times can be 24 hour like *15:30*, or with am or pm like *3:30pm* or *3pm*.
"Tell", "notify" and "message" all work for notifying, as do "that" and "saying" before the message.
A recipient can be named by their full name, alias, or just their first name when no one else shares it -
if two do, the agent asks which one you mean.
Snoozes and silences are for the person asking, when Supernotify can match their Home Assistant user to
a recipient, otherwise for everyone.

The sentences are English only for now - if you'd like them in your language, please suggest
wording on [GitHub issues](https://github.com/rhizomatics/supernotify/issues).

This functionality is also available to scripts and automations from the `conversation.process` action.

## Further Reading

- [AI Agents for the Smart Home](https://www.home-assistant.io/blog/2024/06/07/ai-agents-for-the-smart-home/) - 2024 vision paper from Home Assistant team
- [Home Assistant MCP](https://www.home-assistant.io/integrations/mcp/) - Official integrations
