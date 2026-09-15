#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'A Mac is required for the .app build. Replit can edit and test the shared code.'
  exit 1
fi
build_python="${SWIFT_BUILD_PYTHON:-python3.12}"
"$build_python" -m PyInstaller --noconfirm --distpath dist --workpath build packaging/Swift.spec
/usr/bin/ditto -c -k --sequesterRsrc --keepParent dist/Swift.app "dist/Swift-macOS-$(uname -m).zip"
echo "Built dist/Swift-macOS-$(uname -m).zip"
