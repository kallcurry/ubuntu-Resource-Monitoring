from dataclasses import replace
import csv
import json

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from pulse_monitor.app import MainWindow, QFileDialog, QSystemTrayIcon
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


def test_frameless_controls_themes_and_close_to_tray(qapp, tmp_path, monkeypatch):
    window = MainWindow(tmp_path, start_worker=False)
    try:
        window.show()
        qapp.processEvents()
        assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
        controls = window.titleBar
        assert controls.isVisible()
        assert controls.geometry().right() == window.width() - 1
        assert controls.geometry().bottom() < window.overview.mapTo(window, QPoint()).y()

        QTest.mouseClick(controls.minBtn, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert window.isMinimized()
        window.restore_window()
        QTest.mouseClick(controls.maxBtn, Qt.MouseButton.LeftButton)
        qapp.processEvents()
        assert window.isMaximized()
        assert controls.maxBtn.toolTip() == "还原"
        QTest.mouseDClick(controls, Qt.MouseButton.LeftButton, pos=QPoint(30, 16))
        qapp.processEvents()
        assert not window.isMaximized()
        assert controls.maxBtn.toolTip() == "最大化"
        window.resize(1100, 780)
        qapp.processEvents()
        assert controls.geometry().right() == window.width() - 1

        window.toggle_theme()
        assert controls.minBtn.normalColor.name().upper() == window.colors["muted"]
        assert controls.closeBtn.accessibleName() == "关闭"

        monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", lambda: True)
        window.settings["tray"] = True
        QTest.mouseClick(controls.closeBtn, Qt.MouseButton.LeftButton)
        assert not window.isVisible()
        assert not window.quitting
        window.restore_window()
        assert window.isVisible()
        window.settings["tray"] = False
        QTest.mouseClick(controls.closeBtn, Qt.MouseButton.LeftButton)
        assert not window.isVisible()
        assert window.quitting
    finally:
        window.request_quit()


def test_rich_pages_selection_charts_and_resource_history(qapp, rich_sample, tmp_path):
    window = MainWindow(tmp_path, start_worker=False)
    try:
        window.show()
        window.on_snapshot(rich_sample)
        qapp.processEvents()
        assert window.pages.count() == 6 and len(window.nav) == 6
        hardware, network, storage = window.hardware_page, window.network_page, window.disk_page
        assert len(hardware.core_grid.values) == 16
        assert hardware.memory.fields['缓存'].text() == '2.0 GiB'
        assert 'Ubuntu' in hardware.system.fields['发行版'].text()
        assert network.table.rowCount() == 2 and storage.table.rowCount() == 2
        row = next(r for r in range(network.table.rowCount()) if network.table.item(r, 0).text() == 'lo')
        network.table.setCurrentCell(row, 0)
        assert network.trend.network == 'lo'
        assert network.details.fields['IPv4'].text() == '127.0.0.1'
        assert network.trend.points[-1][1] == 1024 / 1024**2
        assert network.trend.secondary_points[-1][1] == 1024 / 1024**2
        assert set(storage.partition_widgets) == {'/', '/data'}
        assert storage.trend.points[-1][1] == 2
        assert storage.trend.secondary_points[-1][1] == 1
        window.overview.rank_picker.setCurrentIndex(1)
        assert 'python3' in window.overview.rank_rows[0][0].text()
        window.overview.rank_picker.setCurrentIndex(3)
        assert '/s' in window.overview.rank_rows[0][2].text()
        window.on_snapshot(replace(rich_sample, timestamp=1001))
        assert network.table.selected_name() == 'lo'
        assert all(not s.processes for s in network.trend.history)
        history_size = len(storage.trend.history)
        window.toggle_theme()
        assert len(storage.trend.history) == history_size
        window.go(5)
        window.focus_search()
        assert window.pages.currentIndex() == 1
        window.on_snapshot(replace(rich_sample, timestamp=1002, network_details=(), disks=(), partitions=(), sensors=()))
        assert network.details.fields['网卡'].text() == '—'
        assert not storage.partition_widgets
        assert not network.table.rowCount() and not storage.table.rowCount()
    finally:
        window.request_quit()
