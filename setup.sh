#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PULSE_BOOTSTRAP_PYTHON:-python3}"
if ! "$PYTHON_BIN" -m venv --help >/dev/null 2>&1; then
    echo "需要 Python 3.10+ 与 venv。Ubuntu 可安装 python3-venv 后重试。" >&2
    exit 1
fi
# Reuse a compatible system Qt if present; all added packages go into .venv.
"$PYTHON_BIN" -m venv --system-site-packages "$APP_DIR/.venv"
PIP_CONFIG_FILE=/dev/null "$APP_DIR/.venv/bin/python" -m pip install \
    --index-url https://pypi.org/simple --retries 2 --timeout 30 -r "$APP_DIR/requirements.txt"
echo "安装完成。运行：$APP_DIR/run.sh"
