from dataclasses import replace
import csv
import json

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from pulse_monitor.app import MainWindow, QFileDialog
from pulse_monitor.data import PortInfo


def test_process_search_sort_selection_and_pid_reuse(qapp, sample, tmp_path):
    window = MainWindow(tmp_path, start_worker=False)
    try:
        window.on_snapshot(sample)
        page = window.process_page
        page.search.setText("浏览器")
        assert page.proxy.rowCount() == 1
        assert "浏览器" in page.detail.purpose.text()
        page.search.clear()
        page.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        assert "python3" in page.proxy.index(0, 0).data()
        page.select_key(sample.processes[1].key)
        changed = replace(sample, processes=(replace(sample.processes[0], cpu=1),
                                             replace(sample.processes[1], cpu=40)))
        window.on_snapshot(changed)
        assert page.record.key == sample.processes[1].key
        assert page.detail.fields[0].text() == "40.0%"
        reused = replace(sample.processes[1], created=999)
        window.on_snapshot(replace(sample, processes=(sample.processes[0], reused)))
        assert page.record is None
        assert not page.detail.primary.isEnabled()
        restricted = replace(sample.processes[0], cpu=None, cpu_available=False)
        window.on_snapshot(replace(sample, processes=(restricted,)))
        page.select_key(restricted.key)
        assert page.model.data(page.model.index(0, 1)) == "—"
        assert page.detail.fields[0].text() == "—"
    finally:
        window.request_quit()


def test_port_navigation_pause_and_export(qapp, sample, tmp_path, monkeypatch):
    window = MainWindow(tmp_path, start_worker=False)
    try:
        window.on_snapshot(sample)
        proc = sample.processes[0]
        port = PortInfo("TCP", "127.0.0.1", 3000, proc.pid, proc.name, proc.description, proc.created)
        other = replace(port, port=12345, pid=99999, created=200.0,
                        name="other-service", description="其他系统服务")
        window.on_ports((port, other), "普通用户视图")
        window.go(2)
        window.port_page.search.setText("训练")
        assert window.port_page.proxy.rowCount() == 1
        window.open_port_process()
        assert window.pages.currentIndex() == 1
        assert window.process_page.record.key == proc.key
        window.open_related_ports()
        assert window.pages.currentIndex() == 2
        assert window.port_page.record.key == port.key
        assert window.port_page.proxy.rowCount() == 1
        window.toggle_pause()
        frozen = window.snapshot
        window.on_snapshot(replace(sample, cpu=99))
        assert window.snapshot == frozen
        assert "暂停" in window.overview.live.text()
        window.toggle_pause()
        output = tmp_path / "export.csv"
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(output), ""))
        window.export_processes()
        with output.open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))
        assert "中文描述" in rows[0]
        assert any("训练" in row[1] for row in rows[1:])
    finally:
        window.request_quit()


def test_no_gpu_placeholder_and_corrupted_settings(qapp, sample, tmp_path):
    (tmp_path / "settings.json").write_text("[]")
    window = MainWindow(tmp_path, start_worker=False)
    try:
        window.on_snapshot(sample)
        assert "未检测到" in window.overview.gpu.picker.currentText()
        assert window.overview.gpu.ring.value is None
        window.toggle_theme()
        stored = json.loads((tmp_path / "settings.json").read_text())
        assert stored["theme"] == "light"
        assert window.colors["bg"] == "#F5F5F7"
    finally:
        window.request_quit()


def test_slash_shortcut_does_not_swallow_command_path_input(qapp, tmp_path):
    window = MainWindow(tmp_path, start_worker=False)
    try:
        window.show()
        window.go(1)
        window.process_page.search.setFocus()
        qapp.processEvents()
        QTest.keyClicks(window.process_page.search, "/usr/bin")
        assert window.process_page.search.text() == "/usr/bin"
    finally:
        window.request_quit()
