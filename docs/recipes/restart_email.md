---
tags:
  - automation
  - email
  - html_email
  - template
  - recipe
description: Send an automated HTML formatted email notification whenever Home Assistant restarts using Supernotify
---
# Recipe - Home Assistant Restart

## Purpose

Send an email when Home Assistant restarts with some basic information about the installation.

## Implementation

An HTML template is used to pull in values from Home Assistant's self-monitoring entities.

## Example Configuration

```yaml title="default.html.j2"
automations:
- id: notify-restart
  alias: Notify on HomeAssistant start up
  triggers:
    - event: start
      trigger: homeassistant
  action:
      action: notify.supernotifier
      data_template:
        title: "Home Assistant Restart"
        message: "Home Assistant has started up."
        data:
          message_html: |
            <table>
              <tr>
                <th>Component</th><th>Installed Version</th><th>Latest Version</th>
              </tr>
              <tr>
                <td>Core</td>
                <td>{{ states.update.home_assistant_supervisor_update.attributes['installed_version']}}</td>
                <td>{{ states.update.home_assistant_supervisor_update.attributes['latest_version']}}</td>
              </tr>
              <tr>
                <td>Supervisor</td>
                <td>{{ states.update.home_assistant_core_update.attributes['installed_version']}}</td>
                <td>{{ states.update.home_assistant_core_update.attributes['latest_version']}}</td>
                </tr>
              <tr>
                <td>OS</td>
                <td>{{ states.update.home_assistant_operating_system_update.attributes['installed_version']}}</td>
                <td>{{ states.update.home_assistant_operating_system_update.attributes['latest_version']}}</td>
              </tr>
            <table>
```
