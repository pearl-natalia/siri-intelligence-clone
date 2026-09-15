#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Darwin ]]; then
  echo 'A Mac is required for the .app build. Replit can edit and test the shared code.'
  exit 1
fi
build_python="${SWIFT_BUILD_PYTHON:-python3.12}"
mac_stage="$(mktemp -d "${TMPDIR:-/tmp}/swift-build.XXXXXX")"
trap 'rm -rf "$mac_stage"' EXIT
"$build_python" -m PyInstaller --noconfirm --distpath "$mac_stage" --workpath build packaging/Swift.spec
# Finder metadata from iCloud-backed checkouts is not valid in a signed app.
/usr/bin/xattr -dr com.apple.FinderInfo "$mac_stage/Swift.app" 2>/dev/null || true
/usr/bin/xattr -dr com.apple.ResourceFork "$mac_stage/Swift.app" 2>/dev/null || true
/usr/bin/codesign --force --deep --sign "${SWIFT_CODESIGN_IDENTITY:--}" --entitlements packaging/entitlements.plist "$mac_stage/Swift.app"
/usr/bin/codesign --verify --deep --strict "$mac_stage/Swift.app"
mkdir -p dist
/usr/bin/ditto -c -k --sequesterRsrc --keepParent "$mac_stage/Swift.app" "dist/Swift-macOS-$(uname -m).zip"
echo "Built dist/Swift-macOS-$(uname -m).zip"
