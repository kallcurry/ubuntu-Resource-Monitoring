"""Start the native application, or collect a non-identifying diagnostic summary."""

import argparse
import json
import os
from pathlib import Path
import signal
import sys


def main():
    from . import __version__
    parser = argparse.ArgumentParser(description="脉冲 Pulse · Ubuntu 资源监控")
    parser.add_argument("--version", action="version", version=f"Pulse Monitor {__version__}")
    parser.add_argument("--config-dir", help="设置保存目录")
    parser.add_argument("--diagnose", action="store_true", help="采集一次能力诊断摘要后退出")
    parser.add_argument("--quit-after", type=float, help="指定秒数后退出，供验证使用")
    parser.add_argument("--screenshot-dir", help="验证用：导出三个原生页面截图（包含本机真实数据）")
    args = parser.parse_args()
    if args.diagnose:
        from .collectors import Collector
        collector = Collector()
        try:
            snapshot = collector.collect()
            ports, note = collector.ports()
            print(json.dumps({"threads": snapshot.cores, "memory_bytes": snapshot.memory_total,
                              "processes": len(snapshot.processes), "bound_endpoints": len(ports),
                              "gpu_count": len(snapshot.gpus), "gpu_metrics": [
                                  {"utilization": g.utilization is not None,
                                   "vram": g.total is not None} for g in snapshot.gpus],
                              "port_note": note,
                              "collection_ms": round(snapshot.duration*1000)},
                             ensure_ascii=False, indent=2))
        finally:
            collector.close()
        return 0
    # Keep pyqtgraph on the same Qt binding as the Fluent/PySide6 controls.
    os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from .app import MainWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Pulse Monitor")
    app.setOrganizationName("Pulse")
    window = MainWindow(args.config_dir)
    window.show()
    signal.signal(signal.SIGINT, lambda *_: window.request_quit())
    # Let Python handle Ctrl+C even when Qt has no pending events.
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(500)
    if args.screenshot_dir:
        destination = Path(args.screenshot_dir)
        destination.mkdir(parents=True, exist_ok=True)

        def capture():
            if window.snapshot is None:
                QTimer.singleShot(1000, capture)
                return
            if not window.paused:
                window.toggle_pause()
            for index, name in enumerate(("overview", "processes", "ports")):
                window.go(index)
                app.processEvents()
                window.grab().save(str(destination / f"pulse-native-{name}.png"))
            window.go(0)
        QTimer.singleShot(6500, capture)
    if args.quit_after:
        QTimer.singleShot(int(args.quit_after*1000), window.request_quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
