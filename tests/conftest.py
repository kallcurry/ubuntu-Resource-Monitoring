import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    yield app


@pytest.fixture
def sample():
    from pulse_monitor.data import ProcessInfo, Snapshot
    a = ProcessInfo(12345, 100.0, "python3", "Python 训练脚本", "demo", os.getuid(),
                    "python3 train.py", "running", 31.2, 2*1024**3, None)
    b = ProcessInfo(23456, 101.0, "chrome", "谷歌浏览器", "demo", os.getuid(),
                    "chrome", "sleeping", 3.4, 768*1024**2, None)
    return Snapshot(1000.0, 1800000000.0, 35.0, 8, 3600.0, None,
                    16*1024**3, 8*1024**3, 0, 2*1024**3, "eth0", ("eth0",),
                    1024.0, 512.0, 50*1024**3, 200*1024**3,
                    1000.0, 500.0, (), (a, b), 7200, .05)
