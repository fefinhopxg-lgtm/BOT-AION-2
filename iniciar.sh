#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv --system-site-packages .venv
fi
if ! .venv/bin/python -c 'import PIL, dbus_next' 2>/dev/null; then
    .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python -m aion_healer.app
