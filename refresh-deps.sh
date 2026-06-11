#!/bin/bash
echo ensure autobut PRs pulled in
git pull
echo uv sync for main, dev, docs
uv sync --dev --group docs --upgrade

echo "Pre-commit autoupdate ..."
pre-commit autoupdate
