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


@pytest.fixture
def rich_sample(sample):
    from dataclasses import replace
    from pulse_monitor.data import DiskInfo, GPUInfo, HardwareInfo, NetworkInfo, PartitionInfo, SensorInfo
    gib = 1024**3
    return replace(sample, cores=16,
                   hardware=HardwareInfo('AMD Ryzen · 示例工作站', 8, 'Ubuntu 24.04 LTS', '6.8.0', 'x86_64'),
                   cpu_per_core=tuple(float((i * 11) % 100) for i in range(16)),
                   load_average=(1.2, 1.1, .9), memory_cached=2*gib, memory_buffers=128*1024**2,
                   memory_free=6*gib,
                   network_details=(NetworkInfo('eth0', True, 1000, 1500, ('192.0.2.2',), ('2001:db8::2',),
                                                download=2*1024**2, upload=512*1024, received=10*gib, sent=gib),
                                    NetworkInfo('lo', True, mtu=65536, ipv4=('127.0.0.1',),
                                                download=1024, upload=1024, received=2*gib, sent=2*gib)),
                   disks=(DiskInfo('nvme0n1', 2*1024**2, 1024**2, 40, 20, 30),
                          DiskInfo('sda', 512*1024, 0, 10, 0, 2)),
                   partitions=(PartitionInfo('/', '/dev/nvme0n1p2', 'ext4', 200*gib, 50*gib, 140*gib, 25),
                               PartitionInfo('/data', '/dev/sda1', 'ext4', 100*gib, 70*gib, 25*gib, 70)),
                   sensors=(SensorInfo('coretemp · Package', 55, 90, 100),),
                   gpus=(GPUInfo('demo-gpu', '示例 GPU', 32, 2*gib, 8*gib, 60, 80, 40),),
                   processes=tuple(replace(p, threads=8, parent_pid=1, read_rate=1024, write_rate=2048)
                                   for p in sample.processes))
