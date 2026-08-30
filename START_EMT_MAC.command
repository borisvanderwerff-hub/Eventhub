
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

python_bin="$(command -v python3 || true)"
if [ -z "$python_bin" ]; then
    echo "Python 3 is required. Install Python 3.12 from https://www.python.org/downloads/macos/ and try again."
    read -r -p "Press Enter to close..." _
    exit 1
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
    echo "Python 3.12 or newer is required. Install it from https://www.python.org/downloads/macos/ and try again."
    read -r -p "Press Enter to close..." _
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    "$python_bin" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

if ! .venv/bin/python -c 'import PySide6, openpyxl, xlrd' 2>/dev/null; then
    .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python bezoekerslijst_app.py
