"""Absolute-import entry point for the standalone executable."""
import os

os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"

from pulse_monitor.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
