#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${PULSE_PYTHON:-}" ]]; then
    PYTHON_BIN="$PULSE_PYTHON"
elif [[ -x "$APP_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$APP_DIR/.venv/bin/python"
else
    PYTHON_BIN=python3
fi
if ! "$PYTHON_BIN" -c 'import PySide6, psutil, qfluentwidgets, pyqtgraph' >/dev/null 2>&1; then
    echo "首次使用请先运行：$APP_DIR/setup.sh" >&2
    exit 1
fi
cd "$APP_DIR"
export PYQTGRAPH_QT_LIB=PySide6
# Avoid loading Qt plugins from unrelated virtual environments (e.g. OpenCV).
unset QT_QPA_PLATFORM_PLUGIN_PATH
exec "$PYTHON_BIN" -m pulse_monitor "$@"
