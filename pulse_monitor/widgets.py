"""Rounded native panels and real-time plot widgets."""

from collections import deque
from dataclasses import replace
import math

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QToolTip,
    QVBoxLayout, QWidget,
)
from qfluentwidgets import ComboBox

from .data import Snapshot, percent, rate, size


def label(text="", role=None, *, wrap=False):
    widget = QLabel(str(text))
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if role:
        widget.setProperty("role", role)
    return widget


def panel(parent=None):
    frame = QFrame(parent)
    frame.setProperty("role", "card")
    return frame


def vbox(widget, margins=(16, 15, 16, 15), spacing=10):
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


def hbox(widget=None, margins=(0, 0, 0, 0), spacing=10):
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


class MetricCard(QFrame):
    clicked = Signal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setProperty("role", "card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title + "资源卡片")
        self.setMinimumWidth(150)
        self.setFixedHeight(110)
        layout = vbox(self, (14, 12, 14, 12), 5)
        self.title = label(title, "muted")
        self.value = label("采样中", "value")
        self.caption = label("等待首次采样", "muted", wrap=True)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.caption)

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)


class Ring(QWidget):
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.colors = colors
        self.value = None
        self.setFixedSize(94, 94)
        self.setAccessibleName("GPU 计算利用率")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(6, 6, 82, 82)
        painter.setPen(QPen(QColor(self.colors["raised"]), 5))
        painter.drawEllipse(rect)
        if self.value is not None:
            pen = QPen(QColor(self.colors["purple"]), 5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, 90*16, -int(max(0, min(100, self.value))*3.6*16))
        painter.setPen(QColor(self.colors["text"]))
        font = QFont(self.font())
        font.setPixelSize(23)
        painter.setFont(font)
        value = "—" if self.value is None else f"{self.value:.0f}%"
        painter.drawText(QRectF(0, 25, 94, 34), Qt.AlignmentFlag.AlignCenter, value)
        font.setPixelSize(9)
        painter.setFont(font)
        painter.setPen(QColor(self.colors["muted"]))
        painter.drawText(QRectF(0, 59, 94, 15), Qt.AlignmentFlag.AlignCenter, "计算利用率")


class AgoAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return ["现在" if abs(v) < 1 else f"{v/60:.0f} 分" if abs(v) >= 60 else f"{v:.0f} 秒"
                for v in values]


class TrendPanel(QFrame):
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.setProperty("role", "card")
        self.colors = colors
        self.history = deque(maxlen=1000)
        self.resource = "cpu"
        self.gpu_key = ""
        self.network = ""
        self.disk_name = ""
        self.seconds = 60
        self.points = []
        self.secondary_points = []
        layout = vbox(self, (16, 14, 16, 10), 5)
        top = hbox()
        headings = QVBoxLayout()
        headings.setSpacing(4)
        headings.addWidget(label("负载趋势", "section"))
        self.subtitle = label("CPU · 整机总算力为 100%", "muted")
        headings.addWidget(self.subtitle)
        top.addLayout(headings, 1)
        self.range_buttons = []
        for minutes in (1, 5, 15):
            button = QPushButton(f"{minutes} 分钟")
            button.setProperty("variant", "segment")
            button.setCheckable(True)
            button.setChecked(minutes == 1)
            button.clicked.connect(lambda checked=False, m=minutes: self.set_range(m*60))
            top.addWidget(button)
            self.range_buttons.append(button)
        layout.addLayout(top)
        self.current = label("采样中", "purpose")
        layout.addWidget(self.current)
        self.plot = pg.PlotWidget(axisItems={"bottom": AgoAxis(orientation="bottom")})
        self.plot.setMinimumHeight(135)
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.showGrid(x=False, y=True, alpha=.18)
        self.plot.setClipToView(True)
        self.plot.getPlotItem().setContentsMargins(0, 0, 0, 0)
        self.plot.getPlotItem().getAxis("left").setWidth(38)
        self.curve = self.plot.plot(connect="finite")
        self.secondary_curve = self.plot.plot(connect="finite")
        self.marker = self.plot.plot(symbol="o", symbolSize=5, pen=None)
        self.plot.scene().sigMouseMoved.connect(self.hover)
        layout.addWidget(self.plot, 1)
        self.set_theme()

    def set_theme(self):
        self.plot.setBackground(self.colors["surface"])
        for side in ("left", "bottom"):
            axis = self.plot.getPlotItem().getAxis(side)
            axis.setPen(pg.mkPen(self.colors["line"]))
            axis.setTextPen(pg.mkPen(self.colors["subtle"]))
            font = QFont()
            font.setPixelSize(9)
            axis.setTickFont(font)
        self.render()

    def set_range(self, seconds):
        self.seconds = seconds
        for button, minutes in zip(self.range_buttons, (1, 5, 15)):
            button.setChecked(minutes*60 == seconds)
        self.render()

    def append(self, snapshot):
        # Charts retain only resource history, never hundreds of process rows
        # for every tick of a fifteen-minute session.
        self.history.append(replace(snapshot, processes=(), cpu_per_core=(), partitions=(), sensors=()))
        cutoff = snapshot.timestamp - 900
        while self.history and self.history[0].timestamp < cutoff:
            self.history.popleft()
        self.render()

    def render(self):
        mapping = {"cpu": ("CPU · 整机总算力为 100%", "accent"),
                   "memory": ("内存 · 按 total − available 统计", "green"),
                   "gpu": ("GPU · 计算利用率", "purple"),
                   "network": (f"下载（蓝）/ 上传（绿）· {self.network or '自动网卡'}", "blue"),
                   "disk": (f"读取（橙）/ 写入（紫）· {self.disk_name or '选择设备'}", "accent")}
        title, color = mapping[self.resource]
        self.subtitle.setText(title)
        points = []
        secondary = []
        if self.history:
            now = self.history[-1].timestamp
            previous = None
            for sample in self.history:
                if now-sample.timestamp > self.seconds:
                    continue
                other = None
                if self.resource == "cpu":
                    value = sample.cpu
                elif self.resource == "memory":
                    value = sample.memory_percent
                elif self.resource == "network":
                    nic = next((n for n in sample.network_details if n.name == self.network), None)
                    value = nic.download if nic else sample.download if sample.network == self.network else None
                    other = nic.upload if nic else sample.upload if sample.network == self.network else None
                    if value is not None:
                        value /= 1024**2
                    if other is not None:
                        other /= 1024**2
                elif self.resource == "disk":
                    disk = next((d for d in sample.disks if d.name == self.disk_name), None)
                    value = disk.read_rate / 1024**2 if disk and disk.read_rate is not None else None
                    other = disk.write_rate / 1024**2 if disk and disk.write_rate is not None else None
                else:
                    gpu = next((g for g in sample.gpus if g.key == self.gpu_key), None)
                    value = gpu.utilization if gpu else None
                x = sample.timestamp-now
                if previous is not None and sample.timestamp-previous > 7:
                    points.append((x-.01, math.nan))
                    secondary.append((x-.01, math.nan))
                points.append((x, value if value is not None else math.nan))
                secondary.append((x, other if other is not None else math.nan))
                previous = sample.timestamp
        self.points = points
        self.secondary_points = secondary
        x = [p[0] for p in points]
        y = [p[1] for p in points]
        c = QColor(self.colors[color])
        fill = QColor(c)
        fill.setAlpha(16)
        self.curve.setData(x, y, pen=pg.mkPen(c, width=2), fillLevel=0, brush=fill)
        self.secondary_curve.setData([p[0] for p in secondary], [p[1] for p in secondary],
                                     pen=pg.mkPen(self.colors['green' if self.resource == 'network' else 'purple'], width=2))
        finite = [(a, b) for a, b in points if math.isfinite(b)]
        other_finite = [(a, b) for a, b in secondary if math.isfinite(b)]
        throughput = self.resource in ('network', 'disk')
        if finite:
            a, b = finite[-1]
            self.marker.setData([a], [b], symbolBrush=c, symbolPen=None)
            self.current.setText(f"{points[-1][1]:.1f}%" if math.isfinite(points[-1][1]) else '当前指标不可用')
        else:
            self.marker.clear()
            self.current.setText("等待采样" if self.resource != "gpu" else "当前指标不可用")
        if throughput:
            first = rate(points[-1][1] * 1024**2) if points and math.isfinite(points[-1][1]) else '—'
            second = rate(secondary[-1][1] * 1024**2) if secondary and math.isfinite(secondary[-1][1]) else '—'
            self.current.setText(f"{'下载' if self.resource == 'network' else '读取'} {first}    "
                                 f"{'上传' if self.resource == 'network' else '写入'} {second}")
        self.plot.setXRange(-self.seconds, 0, padding=0)
        axis = self.plot.getPlotItem().getAxis('left')
        axis.setLabel(text='MiB/s' if throughput else '', color=self.colors['subtle'])
        axis.setWidth(55 if throughput else 38)
        ymax = max([v for _, v in finite + other_finite] + [.01])*1.2 if throughput else 100
        self.plot.setYRange(0, ymax, padding=0)

    def hover(self, position):
        if not self.plot.sceneBoundingRect().contains(position) or not self.points:
            return
        x = self.plot.getPlotItem().vb.mapSceneToView(position).x()
        point = min(self.points, key=lambda p: abs(p[0]-x))
        if math.isfinite(point[1]):
            unit = "MiB/s" if self.resource in ('network', 'disk') else "%"
            text = f"{point[0]:.0f} 秒 · {point[1]:.2f} {unit}"
            if self.resource in ('network', 'disk') and self.secondary_points:
                other = min(self.secondary_points, key=lambda p: abs(p[0]-x))
                text += f" / {other[1]:.2f} {unit}" if math.isfinite(other[1]) else ' / —'
            QToolTip.showText(QCursor.pos(), text, self)


class GPUCard(QFrame):
    changed = Signal(str)

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.setProperty("role", "card")
        self.colors = colors
        self.gpus = ()
        self.setMinimumHeight(244)
        layout = vbox(self, (14, 12, 14, 12), 7)
        layout.addWidget(label("GPU 工作状态", "section"))
        self.picker = ComboBox()
        self.picker.setMinimumWidth(180)
        self.picker.setFixedHeight(30)
        self.picker.currentIndexChanged.connect(self._changed)
        layout.addWidget(self.picker)
        row = hbox(spacing=12)
        self.ring = Ring(colors)
        row.addWidget(self.ring)
        memory = QVBoxLayout()
        memory.addWidget(label("专用显存", "muted"))
        self.memory = label("—")
        self.memory.setWordWrap(True)
        memory.addWidget(self.memory)
        self.memory_percent = label("等待采样", "muted")
        memory.addWidget(self.memory_percent)
        row.addLayout(memory, 1)
        layout.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)
        self.sensors = label("温度 — · 功耗 —", "muted", wrap=True)
        layout.addWidget(self.sensors)
        self.note = label("等待采样", "muted", wrap=True)
        self.note.setStyleSheet("font-size: 9px;")
        layout.addWidget(self.note)
        layout.addStretch(1)

    @property
    def selected(self):
        key = self.picker.currentData()
        return next((g for g in self.gpus if g.key == key), None)

    def update_gpus(self, gpus, note=""):
        key = self.picker.currentData()
        old = [self.picker.itemData(i) for i in range(self.picker.count())]
        self.gpus = gpus
        if old != [g.key for g in gpus] or not self.picker.count():
            self.picker.blockSignals(True)
            self.picker.clear()
            for g in gpus:
                self.picker.addItem(g.name, userData=g.key)
            if not gpus:
                self.picker.addItem("未检测到可读 GPU", userData="")
            index = self.picker.findData(key)
            self.picker.setCurrentIndex(max(0, index))
            self.picker.blockSignals(False)
        self.picker.setEnabled(bool(gpus))
        self._render(note)

    def _changed(self, index):
        self._render()
        self.changed.emit(self.picker.currentData() or "")

    def _render(self, no_gpu_note=""):
        gpu = self.selected
        self.ring.value = gpu.utilization if gpu else None
        self.ring.update()
        self.memory.setText(f"{size(gpu.used)} / {size(gpu.total)}" if gpu else "—")
        ratio = gpu.used/gpu.total if gpu and gpu.total and gpu.used is not None else None
        self.memory_percent.setText(f"已使用 {ratio*100:.1f}%" if ratio is not None else "指标未提供")
        self.bar.setValue(int(ratio*1000) if ratio is not None else 0)
        self.bar.setEnabled(ratio is not None)
        self.bar.setStyleSheet(f"QProgressBar::chunk {{background:{self.colors['purple']};}}")
        temp = f"{gpu.temperature:.0f} °C" if gpu and gpu.temperature is not None else "—"
        power = f"{gpu.power:.0f} W" if gpu and gpu.power is not None else "—"
        fan = f"{gpu.fan:.0f}%" if gpu and gpu.fan is not None else "—"
        self.sensors.setText(f"{temp}  ·  {power}  ·  风扇 {fan}")
        self.note.setText(gpu.note if gpu else no_gpu_note or "显卡或驱动未提供监控接口")


class SummaryCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setProperty("role", "card")
        layout = vbox(self, (15, 10, 15, 10), 3)
        layout.addWidget(label(title, "muted"))
        self.value = label("采样中", "value")
        self.value.setStyleSheet("font-size:22px;")
        layout.addWidget(self.value)
        self.setFixedHeight(80)
