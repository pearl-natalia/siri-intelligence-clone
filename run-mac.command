#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'The desktop app requires macOS. Use Run in Replit for the browser demo.'
  exit 1
fi
python_bin="${SWIFT_PYTHON:-python3.12}"
if ! command -v "$python_bin" >/dev/null; then
  echo 'Install Python 3.12 from python.org, then run this launcher again.'
  exit 1
fi
"$python_bin" -m venv .venv-mac
.venv-mac/bin/python -m pip install --disable-pip-version-check -r packaging/requirements-mac.txt
exec .venv-mac/bin/python desktop.py
