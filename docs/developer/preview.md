---
tags:
  - developer
  - preview
  - ha-repl
description: A Docker Home Assistant running the checkout's Supernotify, for UI testing and previews
---
# Preview Environment

A Home Assistant in Docker, running this checkout's Supernotify, for trying out the UI, previewing changes, and checking behaviour on a real instance, by hand or by an AI agent using [ha-repl](ha_repl.md). It needs Docker, or OrbStack on a Mac.

## Starting

```bash
docker compose -f preview/compose.yaml up -d
```

The first start also seeds it as the [preview house](#the-preview-house), once Home Assistant is up, which takes a minute or so - `docker compose -f preview/compose.yaml logs seed` says when it's done. Then log in at http://localhost:9123 as `alice`, the admin, or `bob`, both with the password `preview`. Later starts leave the house as it is.

Supernotify is mounted read-only from the checkout, so restart the container to pick up code changes. `docker compose -f preview/compose.yaml down` stops it, keeping its state for next time.

| Environment variable | Default  | Picks                                                                     |
|----------------------|----------|---------------------------------------------------------------------------|
| `HA_VERSION`         | `stable` | The Home Assistant image tag, e.g. `2026.5` for the oldest supported      |
| `HA_PORT`            | `9123`   | The port Home Assistant is on                                             |
| `HA_REPL_VERSION`    | `0.14.1` | The `ha_repl_server` release, which has to match `homeassistant_repl` in `uv.lock` |

## The Preview House

The `seed` service runs `preview/seed.py`, which sets up a fresh preview as `preview_house`, from
`tests/components/supernotify/integration/houses.py`. The integration tests use the same house, in
`test_preview_house.py`, so what's seen in the preview is what's tested.

It has only what a Docker Home Assistant can really have, with no fakes:

- the `demo` integration's cameras, media players, `notify.notifier` entity, sirens and switches
- two floors and five areas, three of them the `demo` integration's own
- `alice` and `bob`, each with a Person, and no mobile apps, e-mail addresses or phone numbers
- two PIRs, `binary_sensor.hall_pir` and `binary_sensor.garden_pir`, as template helpers
- Supernotify with no YAML, so only its own discovered deliveries

Mobile push, Alexa and the other transports needing real devices or accounts aren't there. Add them by hand for a session, or as recipients in the UI, but anything that needs to be in every preview has to be in `preview_house` and its tests too.

The top-level `supernotify:` YAML is `preview/homeassistant/supernotify.yaml`, empty to start with.

## Starting Again

```bash
mise run clean
```

stops the preview and deletes all its Home Assistant state, leaving only the committed `configuration.yaml`, so the next start seeds a fresh preview house.

## ha-repl

The preview runs the `ha_repl_server` component, installed from its GitHub release when the container starts, so the live and exec modes of [ha-repl](ha_repl.md), and an agent using them, reach the running preview, with the Supernotify plugin's variables. Seeding leaves a long-lived token for `alice` in `preview/homeassistant/.preview_token`. Name the preview as a server in `~/.config/ha-repl/config.toml` with it:

```toml
[servers.preview]
url = "http://localhost:9123"
token_command = "cat /path/to/supernotify/preview/homeassistant/.preview_token"
```

```bash
uv run ha-repl --server preview --json exec - <<'PY'
sorted(deliveries)
PY
```
