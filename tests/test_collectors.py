from dataclasses import replace
from types import SimpleNamespace
import os
import socket
import subprocess
import sys
import time

import psutil
import pytest

from pulse_monitor.collectors import Collector, NvidiaProvider, counter_rate, terminate_process
from pulse_monitor.data import PortInfo
from pulse_monitor.descriptions import describe, display_command


def test_descriptions_do_not_guess_generic_runtime_purpose():
    assert "训练" in describe("python3.13", ["python3", "/project/train.py"])
    assert "待识别" in describe("python3", ["python3", "-c", "print(1)"])
    assert "开发服务器" in describe("node", ["node", "/project/node_modules/vite/bin/vite.js"])
    assert "浏览器" in describe("chrome")
    assert describe("unfamiliar-program-xyz") == "用途待识别"
    assert "abc123" not in display_command(["app", "--api-key=abc123"])
    assert "secret123" not in display_command(["app", "--token", "secret123"])


def test_counter_reset_and_ipv6_scope_are_handled():
    assert counter_rate(100, 50, 2) == 25
    assert counter_rate(1, 100, 1) is None
    assert counter_rate(10, 2, 0) is None
    row = PortInfo("TCP", "::1", 3000, None, "受限", "权限不足")
    assert row.scope == "local"
    assert row.endpoint == "[::1]:3000"
    assert replace(row, address="::").scope == "any"
    assert replace(row, address="192.0.2.2").scope == "specific"


def test_gpu_process_memory_deduplicates_compute_and_graphics_lists():
    class FakeNVML:
        class NVMLError(Exception):
            pass
        NVML_TEMPERATURE_GPU = 0
        nvmlDeviceGetCount = staticmethod(lambda: 2)
        nvmlDeviceGetHandleByIndex = staticmethod(lambda i: i)
        nvmlDeviceGetName = staticmethod(lambda h: b"GPU")
        nvmlDeviceGetUtilizationRates = staticmethod(lambda h: SimpleNamespace(gpu=50))
        nvmlDeviceGetMemoryInfo = staticmethod(lambda h: SimpleNamespace(used=256, total=1024))
        nvmlDeviceGetTemperature = staticmethod(lambda h, _: 60)
        nvmlDeviceGetPowerUsage = staticmethod(lambda h: 100000)
        nvmlDeviceGetFanSpeed = staticmethod(lambda h: 30)
        nvmlDeviceGetComputeRunningProcesses = staticmethod(
            lambda h: [SimpleNamespace(pid=42, usedGpuMemory=128)])
        nvmlDeviceGetGraphicsRunningProcesses = staticmethod(
            lambda h: [SimpleNamespace(pid=42, usedGpuMemory=256),
                       SimpleNamespace(pid=99, usedGpuMemory=(1 << 64)-1)])
    provider = NvidiaProvider.__new__(NvidiaProvider)
    provider.api, provider.note = FakeNVML, ""
    gpus, memory, supported = provider.collect()
    assert len(gpus) == 2
    assert memory == {42: 512}  # max(128, 256) on each of two GPUs
    assert supported


def test_real_sampling_first_and_resumed_values_are_not_false_zeroes():
    collector = Collector()
    try:
        first = collector.collect()
        assert first.cpu is None and first.download is None
        assert all(value is None for value in first.cpu_per_core)
        assert first.memory_total > 0
        assert any(p.pid == os.getpid() and p.rss > 0 for p in first.processes)
        time.sleep(.12)
        second = collector.collect()
        assert second.cpu is not None and 0 <= second.cpu <= 100
        assert second.cpu_per_core and all(0 <= value <= 100 for value in second.cpu_per_core)
        assert second.hardware.cpu_model and second.partitions
        assert any(n.name == second.network for n in second.network_details)
        owned = next(p for p in second.processes if p.pid == os.getpid())
        assert owned.threads >= 1 and owned.read_rate is not None
        assert all(p.cpu is None or 0 <= p.cpu <= 100 for p in second.processes)
        collector.reset()
        resumed = collector.collect()
        assert resumed.cpu is None and resumed.disk_read is None
        assert all(p.cpu is None for p in resumed.processes)
        assert all(value is None for value in resumed.cpu_per_core)
        assert all(p.read_rate is None for p in resumed.processes)
        assert all(d.read_rate is None for d in resumed.disks)
    finally:
        collector.close()


def test_owned_tcp_and_udp_sockets_are_found():
    tcp = socket.socket()
    udp = socket.socket(type=socket.SOCK_DGRAM)
    collector = Collector()
    try:
        tcp.bind(("127.0.0.1", 0))
        tcp.listen(1)
        udp.bind(("127.0.0.1", 0))
        collector.collect()
        rows, note = collector.ports()
        for sock, protocol in ((tcp, "TCP"), (udp, "UDP")):
            matches = [p for p in rows if p.port == sock.getsockname()[1] and p.protocol == protocol]
            assert any(p.pid == os.getpid() and p.created is not None for p in matches)
        assert note
    finally:
        tcp.close()
        udp.close()
        collector.close()


def test_termination_rejects_wrong_identity_and_only_ends_owned_test_child():
    child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    try:
        created = psutil.Process(child.pid).create_time()
        with pytest.raises(ValueError, match="复用"):
            terminate_process(child.pid, created-10)
        assert child.poll() is None
        with pytest.raises(ValueError):
            terminate_process(os.getpid(), psutil.Process().create_time())
        terminate_process(child.pid, created)
        child.wait(timeout=5)
        assert child.returncode is not None
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
