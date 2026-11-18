#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DATA_DIR="${XDG_DATA_HOME:-$HOME/.local/share}"
mkdir -p "$APP_DATA_DIR/applications"
APP_ENTRY="$APP_DATA_DIR/applications/pulse-monitor.desktop"
# Quote Desktop Entry argument values; never execute generated desktop data here.
APP_EXEC_PATH="${APP_DIR//\\/\\\\}"
APP_EXEC_PATH="${APP_EXEC_PATH//\"/\\\"}"
APP_EXEC_PATH="${APP_EXEC_PATH//\`/\\\`}"
APP_EXEC_PATH="${APP_EXEC_PATH//\$/\\\$}"
APP_EXEC_PATH="${APP_EXEC_PATH//%/%%}"
cat > "$APP_ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Pulse Monitor
Name[zh_CN]=脉冲资源监控
Comment=Hardware, process and local port monitoring
Comment[zh_CN]=硬件资源、进程中文说明与端口占用查询
Exec="$APP_EXEC_PATH/run.sh"
Icon=$APP_DIR/pulse_monitor/assets/pulse.svg
Terminal=false
Categories=System;Monitor;
StartupNotify=true
EOF
chmod +x "$APP_ENTRY"
echo "已添加到应用菜单：$APP_ENTRY"
