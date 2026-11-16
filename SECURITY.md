# Security Policy

Supernotify follows the [Rhizomatics security policy](https://github.com/rhizomatics/.github/blob/main/SECURITY.md),
which covers supported versions, what belongs with Home Assistant itself, and what to expect from a report.

## Reporting a vulnerability

Please report it privately, from the [Security tab](https://github.com/rhizomatics/supernotify/security) of this
repository, with **Report a vulnerability**. Don't open a public issue, discussion or pull request.

Only the latest release gets security fixes.

## What Supernotify trusts

Supernotify is a Home Assistant custom integration, so it runs inside Home Assistant with everything Home
Assistant can do. It has no login or network service of its own.

- **Administrators** set it up, and are trusted completely.
- **Other Home Assistant users**, and the automations, scripts and apps that call its actions, can send
  notifications and snooze them. Home Assistant lets any user call any action, so they are not trusted with
  the configuration, the archive, or files on the server.
- **The content of a notification** is not trusted at all. Message text, links and images often start outside
  Home Assistant, in an incoming message, a camera, a calendar or an AI agent.

## Measures in place

### In the integration

- Actions that give back configuration or the content of notifications, or that delete or reset, are for
  administrators only: `reload`, `enquire_configuration`, `enquire_archive`, `enquire_last_notification`,
  `purge_archive`, `purge_media`, `clear_snoozes` and `reset_overrides`.
- Passwords, tokens and API keys are left out of the archive, diagnostics, and what those actions give back.
  E-mail addresses and phone numbers are partly masked in diagnostics and debug logs.
- An e-mail only attaches files from the media path, or from folders Home Assistant allows files to be read from.
- A `snapshot_url` is only kept if it is an image, and within a size limit. On new installs it is only
  fetched from Home Assistant's own address and network, or a URL in `allowlist_external_urls`.
- The media path, which is served over the web and cleared of old files, can't be or hold the Home Assistant
  config folder.
- Templates in the message or data of a notify call are not rendered on new installs, only those in the
  configuration. Rendering uses Home Assistant's sandboxed template engine.
- The default e-mail template escapes the message, title and links.
- SMTP connections verify the server's certificate unless that is switched off.
- The tools for AI agents are off until switched on, and can only reach the recipients, deliveries and
  scenarios already configured, not arbitrary addresses, actions or media URLs.
- Calls to other integrations carry the context of whoever sent the notification, so Home Assistant's logbook
  and traces show where each came from.

### In development

- [CodeQL](https://github.com/rhizomatics/supernotify/actions/workflows/codeql.yml) analysis and the
  [OpenSSF Scorecard](https://github.com/rhizomatics/supernotify/actions/workflows/scorecard.yml) run on the
  default branch.
- Dependabot raises dependency and GitHub Action updates, with a cooling-off period for new versions, and
  pull requests get a dependency review.
- Every GitHub Action is pinned to a commit. Workflow tokens have no permissions unless a job needs them, and
  the tests of a pull request run with a read-only token.
- Runtime dependencies are pinned, and kept to versions Home Assistant itself ships.
- Releases are built and published by GitHub Actions, not from a developer's machine.
- Ruff, mypy, Bandit and a test suite with over 90% coverage run on every change, with a regression test for each fix.

## Known limitations

These are on the [roadmap](https://supernotify.rhizomatics.org.uk/latest/developer/roadmap/#security):

- Camera snapshots under the media URL are served without a login, protected only by an id in the file name
  that can't be guessed. Set an empty `media_url_prefix` to switch that off.
- Installs from before v2.19.0 still render templates in notify calls, until *Render Templates in Notify
  Calls* is switched off, and fetch a `snapshot_url` from anywhere, until *Only Local Snapshot URLs* is
  switched on.
- Any phone with the Companion App can snooze notifications for everyone.
- The SMTP password is kept as Home Assistant keeps all credentials, in plain text in its `.storage` folder
  and in backups.
