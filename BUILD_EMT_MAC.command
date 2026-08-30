#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

python_bin="$(command -v python3 || true)"
if [ -z "$python_bin" ]; then
    echo "Python 3.12 or newer is required to build EventHub."
    read -r -p "Press Enter to close..." _
    exit 1
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo "Python 3.12 or newer is required to build EventHub."
    read -r -p "Press Enter to close..." _
    exit 1
fi

if ! xcode-select -p >/dev/null 2>&1; then
    echo "Xcode Command Line Tools are required to build the macOS app."
    echo "Install them with: xcode-select --install"
    read -r -p "Press Enter to close..." _
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    "$python_bin" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
fi

.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/python -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --onedir \
    --name "EventHub" \
    --osx-bundle-identifier "nl.defensie.eventhub" \
    --add-data "templates:templates" \
    --add-data "eventhub_logo.png:." \
    --add-data "eventhub_icon.png:." \
    --add-data "settings_gear.png:." \
    --add-data "server/web/templates:server/web/templates" \
    --add-data "server/web/static:server/web/static" \
    --add-data "server/assets:server/assets" \
    --collect-submodules "server" \
    --icon "eventhub_icon.png" \
    bezoekerslijst_app.py

echo "Created: dist/EventHub.app"
open "dist/EventHub.app"
