"""Single sampling thread; never perform expensive collection in the UI thread."""

import threading
import time

from PySide6.QtCore import QThread, Signal

from .collectors import Collector


class MonitorWorker(QThread):
    snapshotReady = Signal(object)
    portsReady = Signal(object, str)
    failed = Signal(str)

    def __init__(self, interval=1, parent=None):
        super().__init__(parent)
        self.interval = interval
        self.network = ""
        self.paused = False
        self._stop_event = threading.Event()
        self._wake = threading.Event()
        self._refresh = threading.Event()
        self._reset = threading.Event()
        self._lock = threading.Lock()

    def configure(self, *, interval=None, network=None, paused=None):
        with self._lock:
            if interval is not None:
                self.interval = max(1, min(5, interval))
            if network is not None:
                self.network = network
                self._reset.set()
            if paused is not None and paused != self.paused:
                self.paused = paused
                self._reset.set()
        self._wake.set()

    def refresh_ports(self):
        self._refresh.set()
        self._wake.set()

    def stop(self):
        self._stop_event.set()
        self._wake.set()

    def run(self):
        collector = None
        try:
            collector = Collector()
            next_sample = next_ports = 0.0
            while not self._stop_event.is_set():
                with self._lock:
                    interval, network, paused = self.interval, self.network, self.paused
                if self._reset.is_set():
                    self._reset.clear()
                    collector.reset()
                    next_sample = 0
                now = time.monotonic()
                manual = self._refresh.is_set()
                self._refresh.clear()
                if not paused and now >= next_sample:
                    try:
                        self.snapshotReady.emit(collector.collect(network))
                    except Exception as error:
                        self.failed.emit(f"资源采集失败：{type(error).__name__}: {error}")
                    next_sample = time.monotonic() + interval
                if manual or (not paused and now >= next_ports):
                    try:
                        records, note = collector.ports()
                        self.portsReady.emit(records, note)
                    except Exception as error:
                        self.failed.emit(f"端口采集失败：{type(error).__name__}: {error}")
                    next_ports = time.monotonic() + max(4, interval)
                wait = .25 if paused else min(.25, max(.01, next_sample-time.monotonic()))
                self._wake.wait(wait)
                self._wake.clear()
        except Exception as error:
            self.failed.emit(f"监控线程启动失败：{type(error).__name__}: {error}")
        finally:
            if collector:
                collector.close()
