"""The native Pulse desktop application."""

from collections import Counter
from datetime import datetime
import csv
import json
import os
from pathlib import Path
import platform

import psutil
from PySide6.QtCore import Qt, QTimer, Signal, QItemSelectionModel
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QDialog, QFileDialog, QFrame, QHeaderView,
    QHBoxLayout, QLineEdit, QMainWindow, QMenu, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QSystemTrayIcon, QTableView,
    QVBoxLayout, QWidget,
)
from qfluentwidgets import (
    CheckBox, ComboBox, FluentIcon, InfoBar, InfoBarPosition, MessageBox,
    PrimaryPushButton, PushButton, SearchLineEdit, Slider, Theme, setTheme, setThemeColor,
)

from .collectors import terminate_process
from .data import percent, rate, size
from .table_models import PortModel, ProcessModel, RecordProxy, TwoLineDelegate
from .theme import DARK, LIGHT, stylesheet
from .widgets import GPUCard, MetricCard, SummaryCard, TrendPanel, hbox, label, panel, vbox
from .worker import MonitorWorker

ICON_PATH = Path(__file__).parent / "assets/pulse.svg"


def button(text, icon=None, *, primary=False, callback=None):
    widget = PrimaryPushButton(text) if primary else PushButton(text)
    if icon is not None:
        widget.setIcon(icon)
    if callback:
        widget.clicked.connect(callback)
    widget.setFixedHeight(33)
    return widget


def page_header(title, subtitle, eyebrow, *actions):
    widget = QWidget()
    layout = hbox(widget)
    text = QVBoxLayout()
    text.setSpacing(3)
    text.addWidget(label(eyebrow, "eyebrow"))
    text.addWidget(label(title, "title"))
    text.addWidget(label(subtitle, "muted"))
    layout.addLayout(text, 1)
    for action in actions:
        layout.addWidget(action)
    widget.setMinimumHeight(66)
    return widget


class Overview(QWidget):
    processRequested = Signal(object)
    networkChanged = Signal(str)
    pauseRequested = Signal()

    def __init__(self, colors):
        super().__init__()
        self.colors = colors
        self.snapshot = None
        layout = vbox(self, (0, 0, 0, 0), 15)
        self.live = label("正在连接本机", "purpose")
        self.pause = button("暂停", FluentIcon.PAUSE, callback=self.pauseRequested.emit)
        layout.addWidget(page_header("资源总览", "掌握每一份算力，让工作流保持从容。",
                                     "YOUR MACHINE, AT A GLANCE", self.live, self.pause))
        cards = hbox(spacing=12)
        self.metrics = {}
        for key, title in (("cpu", "CPU"), ("memory", "内存"), ("gpu", "GPU"), ("network", "网络")):
            card = MetricCard(title)
            card.clicked.connect(lambda k=key: self.select_resource(k))
            self.metrics[key] = card
            cards.addWidget(card, 1)
        self.metrics["cpu"].set_selected(True)
        layout.addLayout(cards)
        middle = hbox(spacing=14)
        self.trend = TrendPanel(colors)
        middle.addWidget(self.trend, 2)
        self.gpu = GPUCard(colors)
        self.gpu.setMinimumWidth(255)
        self.gpu.changed.connect(self.gpu_changed)
        middle.addWidget(self.gpu, 1)
        layout.addLayout(middle, 1)
        bottom = hbox(spacing=14)
        ranking = panel()
        ranking.setMinimumHeight(154)
        rank_layout = vbox(ranking, (16, 12, 16, 12), 7)
        header = hbox()
        header.addWidget(label("资源占用排行 · CPU", "section"), 1)
        all_button = button("查看全部", FluentIcon.LINK,
                            callback=lambda: self.processRequested.emit(None))
        all_button.setFixedHeight(27)
        header.addWidget(all_button)
        rank_layout.addLayout(header)
        self.rank_rows = []
        for _ in range(3):
            row = hbox(spacing=8)
            name = QPushButton("等待采样")
            name.setFlat(True)
            name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            name.setCursor(Qt.CursorShape.PointingHandCursor)
            name.setStyleSheet("text-align:left;font-size:11px;background:transparent;border:0;")
            name.clicked.connect(lambda checked=False, b=name: self.processRequested.emit(b.property("key")))
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setFixedWidth(80)
            bar.setRange(0, 1000)
            value = label("—", "muted")
            value.setFixedWidth(48)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(name, 1)
            row.addWidget(bar)
            row.addWidget(value)
            rank_layout.addLayout(row)
            self.rank_rows.append((name, bar, value))
        bottom.addWidget(ranking, 2)
        disk = panel()
        disk.setMinimumWidth(255)
        disk_layout = vbox(disk, (16, 12, 16, 12), 9)
        disk_layout.addWidget(label("磁盘与 I/O", "section"))
        self.disk_capacity = label("系统盘 / · 等待采样", "muted", wrap=True)
        disk_layout.addWidget(self.disk_capacity)
        self.disk_bar = QProgressBar()
        self.disk_bar.setTextVisible(False)
        self.disk_bar.setRange(0, 1000)
        disk_layout.addWidget(self.disk_bar)
        self.disk_io = label("整机 I/O · 等待采样", "muted", wrap=True)
        disk_layout.addWidget(self.disk_io)
        self.network_picker = ComboBox()
        self.network_picker.addItem("网卡：自动选择", userData="")
        self.network_picker.setFixedHeight(28)
        self.network_picker.currentIndexChanged.connect(
            lambda: self.networkChanged.emit(self.network_picker.currentData() or ""))
        disk_layout.addWidget(self.network_picker)
        bottom.addWidget(disk, 1)
        layout.addLayout(bottom)

    def select_resource(self, key):
        for resource, metric in self.metrics.items():
            metric.set_selected(resource == key)
        self.trend.resource = key
        self.trend.render()

    def gpu_changed(self, key):
        self.trend.gpu_key = key
        self.trend.render()
        if self.snapshot:
            self._gpu_metric()

    def _gpu_metric(self):
        gpu = self.gpu.selected
        self.metrics["gpu"].value.setText(percent(gpu.utilization) if gpu and gpu.utilization is not None
                                         else "指标未提供" if gpu else "未检测到")
        self.metrics["gpu"].caption.setText(f"显存 {size(gpu.used)} / {size(gpu.total)}" if gpu else "检查显卡与驱动支持")
        self.metrics["gpu"].setToolTip(gpu.name if gpu else self.snapshot.gpu_note)

    def update_snapshot(self, snapshot):
        self.snapshot = snapshot
        self.metrics["cpu"].value.setText(percent(snapshot.cpu))
        frequency = f"{snapshot.frequency/1000:.2f} GHz" if snapshot.frequency else "频率不可读"
        temp = f" · {snapshot.cpu_temperature:.0f} °C" if snapshot.cpu_temperature is not None else ""
        self.metrics["cpu"].caption.setText(f"{snapshot.cores} 线程 · {frequency}{temp}")
        self.metrics["memory"].value.setText(size(snapshot.memory_used))
        self.metrics["memory"].title.setText(f"内存 · {snapshot.memory_percent:.1f}%")
        self.metrics["memory"].caption.setText(f"共 {size(snapshot.memory_total)} · 可用 {size(snapshot.memory_available)}")
        self.metrics["memory"].setToolTip(f"已用 = total − available\nSwap: {size(snapshot.swap_used)} / {size(snapshot.swap_total)}")
        self.metrics["network"].value.setText(rate(snapshot.download))
        self.metrics["network"].caption.setText(f"{snapshot.network} · 上传 {rate(snapshot.upload)}")
        self.gpu.update_gpus(snapshot.gpus, snapshot.gpu_note)
        self._gpu_metric()
        self.trend.gpu_key = self.gpu.selected.key if self.gpu.selected else ""
        self.trend.network = snapshot.network
        self.trend.append(snapshot)
        ranked = sorted(snapshot.processes, key=lambda p: p.cpu if p.cpu is not None else -1, reverse=True)[:3]
        for index, (name, bar, value) in enumerate(self.rank_rows):
            process = ranked[index] if index < len(ranked) else None
            name.setText(f"{process.name} · {process.description}" if process else "无进程数据")
            name.setProperty("key", process.key if process else None)
            name.setToolTip(f"PID {process.pid} · {process.description}" if process else "")
            name.setEnabled(process is not None)
            bar.setValue(int((process.cpu or 0)*10) if process else 0)
            value.setText(percent(process.cpu) if process and process.cpu_available else "—")
        self.disk_capacity.setText(f"系统盘 /  ·  {size(snapshot.disk_used)} / {size(snapshot.disk_total)}")
        self.disk_bar.setValue(int(snapshot.disk_used / snapshot.disk_total * 1000) if snapshot.disk_total else 0)
        self.disk_bar.setStyleSheet(f"QProgressBar::chunk {{background:{self.colors['blue']};}}")
        self.disk_io.setText(f"整机 I/O  读 {rate(snapshot.disk_read)}\n写 {rate(snapshot.disk_write)}")
        old = [self.network_picker.itemData(i) for i in range(self.network_picker.count())]
        if old != [""]+list(snapshot.interfaces):
            key = self.network_picker.currentData()
            self.network_picker.blockSignals(True)
            self.network_picker.clear()
            self.network_picker.addItem("网卡：自动选择", userData="")
            for name in snapshot.interfaces:
                self.network_picker.addItem(f"网卡：{name}", userData=name)
            self.network_picker.setCurrentIndex(max(0, self.network_picker.findData(key)))
            self.network_picker.blockSignals(False)


class DetailPanel(QFrame):
    primaryRequested = Signal()
    copyRequested = Signal()

    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.setProperty("role", "card")
        self.setMinimumWidth(232)
        self.setMaximumWidth(290)
        layout = vbox(self, (14, 14, 14, 14), 10)
        header = hbox()
        header.addWidget(label("进程详情" if kind == "process" else "端口详情", "section"), 1)
        self.state = label("未选择", "badge")
        header.addWidget(self.state)
        layout.addLayout(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        body = vbox(content, (0, 0, 0, 0), 9)
        self.name = label("选择一个条目", "section", wrap=True)
        body.addWidget(self.name)
        self.meta = label("", "muted", wrap=True)
        body.addWidget(self.meta)
        self.purpose = label("中文用途将在这里显示", "purpose", wrap=True)
        body.addWidget(self.purpose)
        body.addWidget(label("启动命令" if kind == "process" else "绑定地址", "muted"))
        self.command = QPlainTextEdit()
        self.command.setReadOnly(True)
        self.command.setProperty("role", "command")
        self.command.setFixedHeight(76 if kind == "process" else 52)
        body.addWidget(self.command)
        self.fields = []
        names = ("CPU · 整机", "物理内存 RSS", "GPU 显存") if kind == "process" else ("所属进程", "PID", "地址范围")
        for title in names:
            row = hbox()
            row.addWidget(label(title, "muted"), 1)
            value = label("—")
            value.setWordWrap(True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(value, 1)
            body.addLayout(row)
            self.fields.append(value)
        self.related = button("查看关联端口", FluentIcon.LINK)
        self.related.setVisible(kind == "process")
        body.addWidget(self.related)
        self.note = label("", "muted", wrap=True)
        self.note.setStyleSheet("font-size:10px;")
        body.addWidget(self.note)
        body.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        if kind == "process":
            actions = hbox(spacing=7)
            self.copy = button("复制 PID", FluentIcon.COPY, callback=self.copyRequested.emit)
            self.primary = button("结束进程", callback=self.primaryRequested.emit)
            self.primary.setObjectName("TerminateButton")
            actions.addWidget(self.copy, 1)
            actions.addWidget(self.primary, 1)
            layout.addLayout(actions)
        else:
            self.primary = button("查看所属进程", FluentIcon.LINK, primary=True,
                                  callback=self.primaryRequested.emit)
            self.copy = button("复制地址", FluentIcon.COPY, callback=self.copyRequested.emit)
            layout.addWidget(self.primary)
            layout.addWidget(self.copy)
        self.clear()

    def clear(self, message="选择一个条目"):
        self.name.setText(message)
        self.meta.setText("")
        self.purpose.setText("中文用途将在这里显示")
        self.command.clear()
        self.state.setText("未选择")
        for value in self.fields:
            value.setText("—")
        self.primary.setEnabled(False)
        self.copy.setEnabled(False)
        self.related.setEnabled(False)
        self.note.setText("可使用搜索框定位进程或端口。")

    def show_record(self, row):
        if row is None:
            self.clear("无匹配条目或条目已退出")
            return
        self.primary.setEnabled(True)
        self.copy.setEnabled(True)
        self.purpose.setText(row.description)
        if self.kind == "process":
            states = {"running": "运行中", "sleeping": "休眠", "disk-sleep": "等待 I/O",
                      "stopped": "已暂停", "zombie": "僵尸进程", "idle": "空闲"}
            self.name.setText(row.name)
            self.meta.setText(f"PID {row.pid} · {row.user}")
            self.command.setPlainText(row.command)
            self.state.setText(states.get(row.status, row.status))
            for widget, value in zip(self.fields, (percent(row.cpu) if row.cpu_available else "—",
                                                   size(row.rss), size(row.vram))):
                widget.setText(value)
            self.primary.setEnabled(row.pid > 1 and row.pid != os.getpid() and row.created is not None)
            self.related.setEnabled(row.created is not None)
            self.note.setText("CPU 按整机算力统计。— 表示权限或驱动未提供该指标。")
        else:
            scopes = {"local": "仅本机回环", "any": "所有网卡", "specific": "指定网卡地址"}
            self.name.setText(str(row.port) + "  " + row.protocol)
            self.meta.setText("TCP 监听" if row.protocol == "TCP" else "UDP 绑定端点")
            self.command.setPlainText(row.endpoint)
            self.state.setText("LISTEN" if row.protocol == "TCP" else "UDP 绑定")
            for widget, value in zip(self.fields, (row.name, str(row.pid) if row.pid else "权限不足", scopes[row.scope])):
                widget.setText(value)
            self.primary.setEnabled(row.pid is not None and row.created is not None)
            self.note.setText("该地址仅供本机访问。" if row.scope == "local"
                              else "外部能否访问还取决于路由与防火墙。")


class TablePage(QWidget):
    selectionChanged = Signal(object)

    def __init__(self, kind, colors):
        super().__init__()
        self.kind = kind
        self.selected_key = None
        self.record = None
        self.initialized = False
        self.layout = vbox(self, (0, 0, 0, 0), 14)
        self.model = ProcessModel(self) if kind == "process" else PortModel(self)
        self.proxy = RecordProxy(kind, self)
        self.proxy.setSourceModel(self.model)
        self.search = SearchLineEdit()
        self.search.setPlaceholderText("搜索进程名称、中文用途、PID 或命令…" if kind == "process"
                                       else "搜索端口、地址、进程或中文用途…")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("搜索进程" if kind == "process" else "搜索端口")
        self.search.textChanged.connect(lambda text: self.filter(query=text))
        self.scope = ComboBox()
        scopes = (("全部进程", "all"), ("我的进程", "me"), ("使用 GPU", "gpu")) if kind == "process" else (
            ("全部地址", "all"), ("仅回环地址", "local"), ("所有网卡", "any"), ("指定网卡地址", "specific"))
        for title, key in scopes:
            self.scope.addItem(title, userData=key)
        self.scope.currentIndexChanged.connect(lambda: self.filter(scope=self.scope.currentData()))
        toolbar = hbox()
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(self.scope)
        if kind == "port":
            self.protocol = ComboBox()
            for title, key in (("全部协议", "all"), ("TCP", "TCP"), ("UDP", "UDP")):
                self.protocol.addItem(title, userData=key)
            self.protocol.currentIndexChanged.connect(lambda: self.filter(protocol=self.protocol.currentData()))
            toolbar.addWidget(self.protocol)
        self.toolbar = toolbar
        content = hbox(spacing=14)
        table_frame = panel()
        table_layout = vbox(table_frame, (1, 1, 1, 0), 0)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1 if kind == "process" else 0,
                                Qt.SortOrder.DescendingOrder if kind == "process" else Qt.SortOrder.AscendingOrder)
        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setMinimumSectionSize(48)
        if kind == "process":
            self.table.setColumnWidth(1, 70)
            self.table.setColumnWidth(2, 88)
            self.table.setColumnWidth(3, 85)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        else:
            for column, width in ((0, 62), (1, 55), (2, 142), (4, 66)):
                self.table.setColumnWidth(column, width)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.delegate = TwoLineDelegate(colors, self.table)
        self.table.setItemDelegateForColumn(0 if kind == "process" else 3, self.delegate)
        self.table.selectionModel().currentRowChanged.connect(self._selection)
        table_layout.addWidget(self.table, 1)
        self.count = label("正在采集…", "muted")
        self.count.setContentsMargins(12, 9, 12, 9)
        self.count.setStyleSheet("font-size:10px;")
        table_layout.addWidget(self.count)
        content.addWidget(table_frame, 1)
        self.detail = DetailPanel(kind)
        content.addWidget(self.detail)
        self.content = content

    def filter(self, **kwargs):
        self.proxy.update_filter(**kwargs)
        self._restore(select_first=True)
        self._count()

    def _selection(self, current, previous=None):
        if current.isValid():
            source = self.proxy.mapToSource(current)
            self.record = self.model.rows[source.row()]
            self.selected_key = self.record.key
        else:
            self.record = None
            self.selected_key = None
        self.detail.show_record(self.record)
        self.selectionChanged.emit(self.record)

    def _restore(self, select_first=False):
        target = None
        if self.selected_key is not None:
            for row, record in enumerate(self.model.rows):
                if record.key == self.selected_key:
                    mapped = self.proxy.mapFromSource(self.model.index(row, 0))
                    if mapped.isValid():
                        target = mapped
                    break
        if target is None and select_first and self.proxy.rowCount():
            target = self.proxy.index(0, 0)
        selection = self.table.selectionModel()
        selection.blockSignals(True)
        if target is not None:
            selection.setCurrentIndex(target, QItemSelectionModel.SelectionFlag.ClearAndSelect |
                                      QItemSelectionModel.SelectionFlag.Rows)
        else:
            selection.clear()
            self.table.setCurrentIndex(self.proxy.index(-1, -1))
        selection.blockSignals(False)
        self._selection(target if target is not None else self.proxy.index(-1, -1))

    def _count(self):
        unit = "个进程" if self.kind == "process" else "条监听 / 绑定记录"
        self.count.setText(f"显示 {self.proxy.rowCount()} / {len(self.model.rows)} {unit}" +
                           ("   ·   CPU 按整机统计" if self.kind == "process" else ""))

    def update_records(self, rows):
        position = self.table.verticalScrollBar().value()
        selection = self.table.selectionModel()
        selection.blockSignals(True)
        self.model.set_rows(rows)
        selection.blockSignals(False)
        self._restore(select_first=not self.initialized)
        if rows:
            self.initialized = True
        self.table.verticalScrollBar().setValue(position)
        self._count()

    def select_key(self, key):
        self.selected_key = key
        self._restore()
        if self.table.currentIndex().isValid():
            self.table.scrollTo(self.table.currentIndex())


class SettingsDialog(QDialog):
    def __init__(self, settings, tray_available, parent):
        super().__init__(parent)
        self.setWindowTitle("偏好设置 · 脉冲")
        self.setMinimumWidth(420)
        layout = vbox(self, (24, 24, 24, 24), 18)
        layout.addWidget(label("偏好设置", "title"))
        layout.addWidget(label("选择更适合你的监控节奏。", "muted"))
        self.interval_label = label(f"刷新间隔 · {settings['interval']} 秒")
        layout.addWidget(self.interval_label)
        self.interval = Slider(Qt.Orientation.Horizontal)
        self.interval.setRange(1, 5)
        self.interval.setValue(settings["interval"])
        self.interval.valueChanged.connect(lambda value: self.interval_label.setText(f"刷新间隔 · {value} 秒"))
        layout.addWidget(self.interval)
        self.tray = CheckBox("关闭窗口后驻留托盘")
        self.tray.setChecked(settings["tray"] and tray_available)
        self.tray.setEnabled(tray_available)
        layout.addWidget(self.tray)
        if not tray_available:
            layout.addWidget(label("当前桌面没有可用的系统托盘，关闭窗口将退出。", "muted", wrap=True))
        layout.addWidget(label("端口每 4–5 秒自动刷新，也可手动刷新。\n所有采集与设置保存在本机。", "muted", wrap=True))
        actions = hbox()
        actions.addStretch(1)
        actions.addWidget(button("取消", callback=self.reject))
        actions.addWidget(button("保存", primary=True, callback=self.accept))
        layout.addLayout(actions)


class MainWindow(QMainWindow):
    def __init__(self, config_dir=None, *, start_worker=True):
        super().__init__()
        self.setWindowTitle("脉冲 Pulse · 系统资源监控")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(1180, 800)
        self.setMinimumSize(1040, 740)
        self.colors = dict(DARK)
        self.config_file = Path(config_dir or Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"pulse-monitor") / "settings.json"
        self.settings = {"theme": "dark", "interval": 1, "tray": False}
        try:
            raw = json.loads(self.config_file.read_text())
            if not isinstance(raw, dict):
                raise ValueError("Invalid settings object")
            self.settings.update(theme="light" if raw.get("theme") == "light" else "dark",
                                 interval=max(1, min(5, int(raw.get("interval", 1)))),
                                 tray=bool(raw.get("tray", False)))
        except (OSError, ValueError, TypeError):
            pass
        self.snapshot = None
        self.ports = ()
        self.paused = False
        self.quitting = False
        self._can_close = False
        root = QWidget()
        root.setObjectName("AppRoot")
        self.setCentralWidget(root)
        body = hbox(root, spacing=0)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(180)
        side = vbox(sidebar, (12, 24, 12, 15), 8)
        brand = hbox(spacing=10)
        logo = label()
        logo.setPixmap(self.windowIcon().pixmap(34, 34))
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(3)
        names.addWidget(label("脉冲", "title"))
        names.addWidget(label("PULSE MONITOR", "eyebrow"))
        brand.addLayout(names, 1)
        side.addLayout(brand)
        side.addSpacing(20)
        side.addWidget(label("工作空间", "eyebrow"))
        self.nav = []
        for index, (text, icon) in enumerate((("资源总览", FluentIcon.HOME), ("进程洞察", FluentIcon.APPLICATION), ("端口查询", FluentIcon.LINK))):
            nav = QPushButton(text)
            nav.setIcon(icon.icon())
            nav.setProperty("variant", "nav")
            nav.setCheckable(True)
            nav.clicked.connect(lambda checked=False, i=index: self.go(i))
            side.addWidget(nav)
            self.nav.append(nav)
        side.addStretch(1)
        host = panel()
        host_layout = vbox(host, (11, 12, 11, 12), 6)
        self.host = label(platform.node() or "本机", "section")
        self.host.setWordWrap(True)
        host_layout.addWidget(self.host)
        self.host_info = label("Ubuntu · 本机实时采集", "muted", wrap=True)
        host_layout.addWidget(self.host_info)
        side.addWidget(host)
        side.addWidget(button("偏好设置", FluentIcon.SETTING, callback=self.open_settings))
        self.theme_button = button("切换浅色", FluentIcon.BRIGHTNESS, callback=self.toggle_theme)
        side.addWidget(self.theme_button)
        body.addWidget(sidebar)
        container = QWidget()
        main = vbox(container, (24, 20, 24, 20), 0)
        self.pages = QStackedWidget()
        self.overview = Overview(self.colors)
        self.overview.pauseRequested.connect(self.toggle_pause)
        self.overview.processRequested.connect(self.open_process)
        self.overview.networkChanged.connect(self.change_network)
        self.process_page = TablePage("process", self.colors)
        self.process_page.layout.addWidget(page_header(
            "进程洞察", "从资源占用到中文用途，一眼找到负载来源。", "FIND WHAT'S WORKING HARD",
            button("导出 CSV", FluentIcon.DOWNLOAD, callback=self.export_processes)))
        summary = hbox(spacing=12)
        self.summaries = []
        for title in ("CPU 总占用", "物理内存", "GPU 显存"):
            card = SummaryCard(title)
            summary.addWidget(card, 1)
            self.summaries.append(card)
        self.process_page.layout.addLayout(summary)
        self.process_page.layout.addLayout(self.process_page.toolbar)
        self.process_page.layout.addLayout(self.process_page.content, 1)
        self.process_page.layout.addWidget(label("支持中文用途搜索 · RSS 含共享页，不能直接相加作为系统内存。", "muted"))
        self.process_page.detail.copyRequested.connect(self.copy_pid)
        self.process_page.detail.primaryRequested.connect(self.confirm_terminate)
        self.process_page.detail.related.clicked.connect(self.open_related_ports)
        self.port_page = TablePage("port", self.colors)
        self.refresh_button = button("刷新", FluentIcon.SYNC, callback=self.refresh_ports)
        self.port_page.layout.addWidget(page_header(
            "端口查询", "端口被谁占用了？从绑定地址直接定位进程。", "EVERY PORT HAS A STORY", self.refresh_button))
        banner = panel()
        banner_layout = vbox(banner, (16, 12, 16, 12), 5)
        self.port_banner = label("正在读取本机监听端口…", "section")
        self.port_permission = label("TCP 监听与 UDP 绑定端点", "muted", wrap=True)
        banner_layout.addWidget(self.port_banner)
        banner_layout.addWidget(self.port_permission)
        self.port_page.layout.addWidget(banner)
        self.port_page.layout.addLayout(self.port_page.toolbar)
        self.port_page.layout.addLayout(self.port_page.content, 1)
        self.port_note = label("— 表示所属进程信息不可读；UDP 显示绑定端点。", "muted")
        self.port_page.layout.addWidget(self.port_note)
        self.port_page.detail.primaryRequested.connect(self.open_port_process)
        self.port_page.detail.copyRequested.connect(self.copy_endpoint)
        for page in (self.overview, self.process_page, self.port_page):
            self.pages.addWidget(page)
        main.addWidget(self.pages)
        body.addWidget(container, 1)
        self.status = label("正在连接本机采集器…", "muted")
        self.statusBar().addWidget(self.status, 1)
        self.statusBar().addPermanentWidget(label("本地实时数据  /  v0.1.0", "muted"))
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("脉冲 Pulse · 系统资源监控")
        menu = QMenu(self)
        show_action = QAction("显示脉冲", menu)
        show_action.triggered.connect(self.restore_window)
        menu.addAction(show_action)
        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.request_quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.restore_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.worker = MonitorWorker(self.settings["interval"], self)
        self.worker.snapshotReady.connect(self.on_snapshot)
        self.worker.portsReady.connect(self.on_ports)
        self.worker.failed.connect(self.on_error)
        self.worker.finished.connect(self._worker_finished)
        self.apply_theme()
        self.go(0)
        self.search_shortcut = QShortcut(QKeySequence("/"), self)
        self.search_shortcut.activated.connect(self.focus_search)
        QApplication.instance().focusChanged.connect(self.update_search_shortcut)
        self.find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.find_shortcut.activated.connect(self.focus_search)
        if start_worker:
            self.worker.start()

    def save_settings(self):
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.config_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2))
            temporary.replace(self.config_file)
        except OSError as error:
            self.notify("设置保存失败", str(error), error=True)

    def apply_theme(self):
        light = self.settings["theme"] == "light"
        self.colors.clear()
        self.colors.update(LIGHT if light else DARK)
        setTheme(Theme.LIGHT if light else Theme.DARK)
        setThemeColor(QColor(self.colors["accent"]))
        self.setStyleSheet(stylesheet(self.colors))
        self.theme_button.setText("切换深色" if light else "切换浅色")
        for nav, icon in zip(self.nav, (FluentIcon.HOME, FluentIcon.APPLICATION, FluentIcon.LINK)):
            nav.setIcon(icon.icon(Theme.LIGHT if light else Theme.DARK))
        self.overview.trend.set_theme()
        self.overview.gpu.ring.update()
        self.process_page.table.viewport().update()
        self.port_page.table.viewport().update()
        self.process_page.detail.primary.setStyleSheet(
            f"PushButton {{color:{self.colors['danger']};border:1px solid {self.colors['danger']};border-radius:8px;}}"
            f"PushButton:disabled {{color:{self.colors['subtle']};border-color:{self.colors['line']};}}")
        if self.snapshot:
            self.overview.gpu._render()

    def toggle_theme(self):
        self.settings["theme"] = "light" if self.settings["theme"] == "dark" else "dark"
        self.apply_theme()
        self.save_settings()

    def go(self, index):
        self.pages.setCurrentIndex(index)
        for i, nav in enumerate(self.nav):
            nav.setChecked(i == index)

    def focus_search(self):
        if self.pages.currentIndex() == 0:
            self.go(1)
        page = self.port_page if self.pages.currentIndex() == 2 else self.process_page
        page.search.setFocus()
        page.search.selectAll()

    def update_search_shortcut(self, previous, current):
        # '/' focuses search when browsing, but remains a normal character in editors.
        self.search_shortcut.setEnabled(not isinstance(current, (QLineEdit, QPlainTextEdit)))

    def on_snapshot(self, snapshot):
        if self.paused:
            return
        self.snapshot = snapshot
        self.overview.update_snapshot(snapshot)
        self.process_page.update_records(snapshot.processes)
        self.summaries[0].value.setText(percent(snapshot.cpu))
        self.summaries[1].value.setText(size(snapshot.memory_used) + " / " + size(snapshot.memory_total))
        used = [g.used for g in snapshot.gpus if g.used is not None]
        total = [g.total for g in snapshot.gpus if g.total is not None]
        self.summaries[2].value.setText(size(sum(used)) + " / " + size(sum(total)) if used and total else "指标未提供")
        self.overview.live.setText(f"实时采样 · {self.settings['interval']} 秒")
        self.host_info.setText(f"{platform.system()} · {snapshot.cores} 线程\n已运行 {int(snapshot.uptime//3600)} 小时 {int(snapshot.uptime%3600//60)} 分钟")
        self.status.setText(f"本机实时数据 · {datetime.fromtimestamp(snapshot.wall_time):%H:%M:%S}   ·   {len(snapshot.processes)} 个进程   ·   采集 {snapshot.duration*1000:.0f} ms")

    def on_ports(self, ports, note):
        self.ports = ports
        self.port_page.update_records(ports)
        counts = Counter(p.protocol for p in ports)
        self.port_banner.setText(f"{len(ports)} 条监听 / 绑定记录   ·   {counts['TCP']} TCP / {counts['UDP']} UDP")
        self.port_permission.setText(note)
        self.port_note.setText(f"更新于 {datetime.now():%H:%M:%S} · UDP 显示绑定端点，受限 PID 显示为“受限”。")
        self.refresh_button.setEnabled(True)

    def on_error(self, message):
        self.status.setText(message)
        self.refresh_button.setEnabled(True)

    def toggle_pause(self):
        self.paused = not self.paused
        self.worker.configure(paused=self.paused)
        self.overview.pause.setText("继续" if self.paused else "暂停")
        self.overview.pause.setIcon(FluentIcon.PLAY if self.paused else FluentIcon.PAUSE)
        self.overview.live.setText("已暂停 · 保留最后快照" if self.paused else "正在恢复采样…")
        if self.paused:
            self.status.setText("采集已暂停 · 当前显示最后一次采样")

    def change_network(self, name):
        self.worker.configure(network=name)

    def refresh_ports(self):
        self.refresh_button.setEnabled(False)
        self.worker.refresh_ports()

    def open_process(self, key=None):
        self.go(1)
        if key is None:
            self.process_page.scope.setCurrentIndex(0)
            self.process_page.search.clear()
        else:
            self.process_page.scope.setCurrentIndex(0)
            self.process_page.search.setText(f"pid:{key[0]}")
            self.process_page.select_key(tuple(key))

    def open_port_process(self):
        port = self.port_page.record
        if not port or port.pid is None or port.created is None:
            return
        if not self.snapshot or not any(p.key == (port.pid, port.created) for p in self.snapshot.processes):
            self.notify("进程已退出", "当前快照中没有匹配的进程，请刷新端口后重试。")
            return
        self.open_process((port.pid, port.created))

    def open_related_ports(self):
        process = self.process_page.record
        if not process:
            return
        self.go(2)
        self.port_page.scope.setCurrentIndex(0)
        self.port_page.protocol.setCurrentIndex(0)
        self.port_page.search.setText(f"pid:{process.pid}")
        matching = next((p for p in self.ports if p.pid == process.pid and p.created == process.created), None)
        if matching:
            self.port_page.select_key(matching.key)
        else:
            self.port_page.detail.clear("没有匹配的监听端口")

    def copy_pid(self):
        if self.process_page.record:
            QApplication.clipboard().setText(str(self.process_page.record.pid))
            self.notify("已复制", "PID 已复制到剪贴板。")

    def copy_endpoint(self):
        if self.port_page.record:
            QApplication.clipboard().setText(self.port_page.record.endpoint)
            self.notify("已复制", "绑定地址已复制到剪贴板。")

    def confirm_terminate(self):
        process = self.process_page.record
        if process is None:
            return
        dialog = MessageBox(f"结束 {process.name}？",
                            f"PID {process.pid} · {process.description}\n{process.command[:350]}\n\n"
                            "将发送 SIGTERM，请先保存工作。此操作不会自动强制结束进程。", self)
        dialog.yesButton.setText("结束进程")
        dialog.cancelButton.setText("取消")
        if dialog.exec():
            try:
                terminate_process(process.pid, process.created)
                self.notify("已发送结束请求", "进程正在处理 SIGTERM；若仍显示，请稍后刷新。")
            except (psutil.NoSuchProcess, psutil.ZombieProcess):
                self.notify("进程已退出", "没有对其他进程执行操作。")
            except (psutil.AccessDenied, PermissionError):
                self.notify("权限不足", "当前用户不能结束这个进程。", error=True)
            except (ValueError, OSError) as error:
                self.notify("操作取消", str(error), error=True)

    def export_processes(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出当前筛选结果", f"pulse-processes-{datetime.now():%Y%m%d-%H%M%S}.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(["进程", "中文描述", "PID", "用户", "CPU整机%", "RSS字节", "显存字节", "命令"])
                for index in range(self.process_page.proxy.rowCount()):
                    source = self.process_page.proxy.mapToSource(self.process_page.proxy.index(index, 0))
                    p = self.process_page.model.rows[source.row()]
                    # CSV text can be opened in spreadsheet software. Prevent formula execution.
                    def text(value):
                        return "'" + value if value.startswith(("=", "+", "-", "@", "\t", "\r")) else value
                    writer.writerow([text(p.name), text(p.description), p.pid, text(p.user),
                                     p.cpu if p.cpu is not None else "", p.rss if p.rss is not None else "",
                                     p.vram if p.vram is not None else "", text(p.command)])
            self.notify("导出完成", f"已保存 {self.process_page.proxy.rowCount()} 个进程。")
        except OSError as error:
            self.notify("导出失败", str(error), error=True)

    def open_settings(self):
        dialog = SettingsDialog(self.settings, QSystemTrayIcon.isSystemTrayAvailable(), self)
        if dialog.exec():
            self.settings.update(interval=dialog.interval.value(), tray=dialog.tray.isChecked())
            self.worker.configure(interval=self.settings["interval"])
            self.save_settings()
            self.notify("设置已保存", f"刷新间隔为 {self.settings['interval']} 秒。")

    def notify(self, title, content, *, error=False):
        method = InfoBar.error if error else InfoBar.success
        method(title=title, content=content, duration=3500, position=InfoBarPosition.BOTTOM_RIGHT, parent=self)

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def request_quit(self):
        self.quitting = True
        self.close()

    def _worker_finished(self):
        if self.quitting:
            self._can_close = True
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event):
        if not self.quitting and self.settings["tray"] and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
            return
        self.quitting = True
        if self.worker.isRunning() and not self._can_close:
            self.status.setText("正在停止后台采集…")
            self.worker.stop()
            event.ignore()
            return
        self.tray.hide()
        event.accept()
