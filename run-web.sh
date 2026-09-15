#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv-web
PIP_USER=false .venv-web/bin/python -m pip install --disable-pip-version-check -q -r requirements-web.txt
exec .venv-web/bin/gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers 1 --threads 4 --timeout 150 web_app:app
