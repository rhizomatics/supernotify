#!/bin/bash
# docker compose for the preview, with ha_repl_server at the version of the ha-repl client in uv.lock
set -euo pipefail
cd "$(dirname "$0")/.."
HA_REPL_VERSION=$(python3 -c "import tomllib; print(next(p['version'] for p in tomllib.load(open('uv.lock', 'rb'))['package'] if p['name'] == 'homeassistant-repl'))")
export HA_REPL_VERSION
exec docker compose -f preview/compose.yaml "$@"
