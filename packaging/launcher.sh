#!/bin/sh
export PYQTGRAPH_QT_LIB=PySide6
unset PYTHONHOME PYTHONPATH QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH
exec /opt/pulse-monitor/PulseMonitor "$@"
