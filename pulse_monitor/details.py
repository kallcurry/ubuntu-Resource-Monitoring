"""Detailed hardware, adapter and storage pages built with native Qt widgets."""

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QGridLayout, QHeaderView, QProgressBar, QScrollArea,
    QTableWidget, QTableWidgetItem, QWidget,
)

from .data import percent, rate, size
from .widgets import SummaryCard, TrendPanel, hbox, label, panel, vbox


def optional_rate(value):
    return rate(value) if value is not None else '—'


def progress():
    widget = QProgressBar()
    widget.setRange(0, 1000)
    widget.setTextVisible(False)
    return widget


class ScrollPage(QWidget):
    def __init__(self, header):
        super().__init__()
        outer = vbox(self, (0, 0, 0, 0), 14)
        outer.addWidget(header)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.body = vbox(content, (0, 0, 8, 0), 14)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)


class InfoCard(QWidget):
    def __init__(self, title, names):
        super().__init__()
        outer = vbox(self, (0, 0, 0, 0), 0)
        frame = panel()
        layout = vbox(frame, (16, 15, 16, 15), 10)
        self.content_layout = layout
        layout.addWidget(label(title, 'section'))
        self.fields = {}
        for name in names:
            row = hbox(spacing=15)
            row.addWidget(label(name, 'muted'))
            value = label('—', wrap=True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(value, 1)
            layout.addLayout(row)
            self.fields[name] = value
        layout.addStretch(1)
        outer.addWidget(frame)

    def update_values(self, values):
        for key, value in values.items():
            self.fields[key].setText(str(value))


class SortItem(QTableWidgetItem):
    def __lt__(self, other):
        return self.data(Qt.ItemDataRole.UserRole) < other.data(Qt.ItemDataRole.UserRole)


class StatsTable(QTableWidget):
    def __init__(self, headers, title):
        super().__init__(0, len(headers))
        self.setAccessibleName(title)
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(38)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setMinimumSectionSize(60)
        self.setMinimumHeight(185)
        self.setMaximumHeight(250)
        self.setSortingEnabled(True)
        self.sortItems(0, Qt.SortOrder.AscendingOrder)

    def selected_name(self):
        item = self.item(self.currentRow(), 0)
        return item.text() if item else ''

    def update_rows(self, rows, preferred=''):
        selected = self.selected_name() or preferred
        scroll = self.verticalScrollBar().value()
        column = self.horizontalHeader().sortIndicatorSection()
        order = self.horizontalHeader().sortIndicatorOrder()
        self.blockSignals(True)
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                text, sort = value if isinstance(value, tuple) else (value, str(value))
                item = SortItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, sort)
                item.setToolTip(str(text))
                if c:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(r, c, item)
        self.setSortingEnabled(True)
        self.sortItems(column, order)
        target = next((r for r in range(self.rowCount()) if self.item(r, 0).text() == selected),
                      0 if rows else -1)
        self.setCurrentCell(target, 0)
        self.verticalScrollBar().setValue(scroll)
        self.blockSignals(False)


class CoreGrid(QWidget):
    def __init__(self, colors):
        super().__init__()
        self.colors = colors
        self.values = ()
        self.setAccessibleName('各逻辑核心 CPU 利用率')

    def set_values(self, values):
        self.values = values
        self.setMinimumHeight(max(48, math.ceil(len(values) / 8) * 46))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(10)
        painter.setFont(font)
        for index, value in enumerate(self.values):
            width = self.width() / 8
            x, y = (index % 8) * width, (index // 8) * 46
            rect = QRectF(x, y, width - 7, 39)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.colors['raised']))
            painter.drawRoundedRect(rect, 6, 6)
            painter.setPen(QColor(self.colors['muted']))
            painter.drawText(rect.adjusted(7, 1, -5, -8), Qt.AlignmentFlag.AlignVCenter,
                             f'{index + 1:02d}  {value:.0f}%' if value is not None else f'{index + 1:02d}  —')
            if value is not None and value > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(self.colors['accent' if value >= 80 else 'green']))
                painter.drawRoundedRect(QRectF(x + 7, y + 30, max(1, (width - 21) * value / 100), 3), 1.5, 1.5)


class HardwarePage(ScrollPage):
    def __init__(self, colors, header):
        super().__init__(header)
        cpu = panel()
        layout = vbox(cpu)
        self.cpu_model = label('正在识别处理器…', 'section', wrap=True)
        self.cpu_caption = label('等待采样', 'muted', wrap=True)
        layout.addWidget(self.cpu_model)
        layout.addWidget(self.cpu_caption)
        layout.addWidget(label('逻辑核心利用率 · 每个核心独立为 100%', 'muted'))
        self.core_grid = CoreGrid(colors)
        layout.addWidget(self.core_grid)
        self.body.addWidget(cpu)
        row = hbox(spacing=14)
        self.memory = InfoCard('内存与交换空间', ('物理内存', '实际已用', '可用内存', '完全空闲', '缓存', '缓冲区', 'Swap'))
        self.memory_bar = progress()
        self.memory.content_layout.insertWidget(1, self.memory_bar)
        self.colors = colors
        self.system = InfoCard('系统信息', ('发行版', '内核', '架构', '物理核心 / 逻辑核心', '平均负载 1 / 5 / 15 分钟', '已运行', '电池'))
        row.addWidget(self.memory, 1)
        row.addWidget(self.system, 1)
        self.body.addLayout(row)
        self.body.addWidget(label('内存已用 = total − available；缓存和缓冲区可能包含在可用内存中，不应重复相加。', 'muted', wrap=True))
        self.gpus = InfoCard('全部 GPU', ('设备与状态',))
        self.body.addWidget(self.gpus)
        self.body.addWidget(label('温度传感器', 'section'))
        self.sensors = StatsTable(('传感器', '当前', '高温参考', '临界参考'), '温度传感器列表')
        self.sensors.setMinimumHeight(150)
        self.body.addWidget(self.sensors)
        self.sensor_note = label('未提供的温度阈值显示 —，具体限制取决于硬件与驱动。', 'muted', wrap=True)
        self.body.addWidget(self.sensor_note)
        self.body.addStretch(1)

    def update_snapshot(self, s):
        self.cpu_model.setText(s.hardware.cpu_model)
        self.cpu_caption.setText(f'{s.cores} 个逻辑核心  ·  当前频率 {s.frequency / 1000:.2f} GHz'
                                 if s.frequency else f'{s.cores} 个逻辑核心  ·  当前频率不可读')
        self.core_grid.set_values(s.cpu_per_core)
        self.memory_bar.setValue(int(s.memory_percent * 10))
        self.memory.update_values({'物理内存': size(s.memory_total), '实际已用': f'{size(s.memory_used)} · {s.memory_percent:.1f}%',
                                   '可用内存': size(s.memory_available), '完全空闲': size(s.memory_free),
                                   '缓存': size(s.memory_cached), '缓冲区': size(s.memory_buffers),
                                   'Swap': f'{size(s.swap_used)} / {size(s.swap_total)}'})
        battery = (f'{s.battery.percent:.0f}% · ' + ('已接电源' if s.battery.plugged else '使用电池')) if s.battery else '未检测到电池'
        self.system.update_values({'发行版': s.hardware.distribution, '内核': s.hardware.kernel,
                                   '架构': s.hardware.architecture,
                                   '物理核心 / 逻辑核心': f'{s.hardware.physical_cores or "—"} / {s.cores}',
                                   '平均负载 1 / 5 / 15 分钟': ' / '.join(f'{n:.2f}' for n in s.load_average) or '—',
                                   '已运行': f'{int(s.uptime // 3600)} 小时 {int(s.uptime % 3600 // 60)} 分钟', '电池': battery})
        lines = []
        for gpu in s.gpus:
            temp = f'{gpu.temperature:.0f} °C' if gpu.temperature is not None else '温度 —'
            power = f'{gpu.power:.0f} W' if gpu.power is not None else '功耗 —'
            util = percent(gpu.utilization) if gpu.utilization is not None else '利用率 —'
            lines.append(f'{gpu.name}\n{util}  ·  显存 {size(gpu.used)} / {size(gpu.total)}  ·  {temp}  ·  {power}')
        self.gpus.update_values({'设备与状态': '\n\n'.join(lines) or s.gpu_note or '未检测到可读 GPU'})
        self.sensors.update_rows([(x.name, (f'{x.temperature:.1f} °C', x.temperature),
                                   (f'{x.high:.0f} °C' if x.high is not None else '—', x.high if x.high is not None else -1),
                                   (f'{x.critical:.0f} °C' if x.critical is not None else '—', x.critical if x.critical is not None else -1)) for x in s.sensors])
        self.sensor_note.setText('未提供的温度阈值显示 —，具体限制取决于硬件与驱动。' if s.sensors else '当前设备或驱动没有提供可读温度传感器。')

    def set_theme(self):
        self.core_grid.update()
        self.memory_bar.setStyleSheet(f"QProgressBar::chunk {{background:{self.colors['green']};}}")


class NetworkPage(ScrollPage):
    def __init__(self, colors, header):
        super().__init__(header)
        self.snapshot = None
        summaries = hbox(spacing=12)
        self.metrics = [SummaryCard(name) for name in ('当前网卡下载', '当前网卡上传', '累计接收', '累计发送')]
        for card in self.metrics:
            summaries.addWidget(card, 1)
        self.body.addLayout(summaries)
        row = hbox(spacing=14)
        self.trend = TrendPanel(colors)
        self.trend.resource = 'network'
        self.trend.setFixedHeight(320)
        row.addWidget(self.trend, 2, Qt.AlignmentFlag.AlignTop)
        self.details = InfoCard('链路详情', ('网卡', '链路状态', 'IPv4', 'IPv6', 'MAC', '链路速率', 'MTU', '收 / 发包数', '错误 / 丢包'))
        self.details.setMinimumWidth(245)
        row.addWidget(self.details, 1)
        self.body.addLayout(row)
        self.body.addWidget(label('全部网络接口 · 点击网卡切换详情和曲线', 'section'))
        self.table = StatsTable(('网卡', '链路', '下载', '上传', '累计接收', '累计发送'), '网卡流量列表')
        self.table.currentCellChanged.connect(self.select_adapter)
        self.body.addWidget(self.table)
        self.body.addWidget(label('流量为接口计数，包含虚拟网卡与回环。累计值来自系统计数器，重启或重建接口后可能重置。链路速率不是实时网速。', 'muted', wrap=True))
        self.body.addStretch(1)

    def select_adapter(self, *args):
        name = self.table.selected_name()
        self.trend.network = name
        self.trend.render()
        self.render_details()

    def render_details(self):
        if not self.snapshot:
            return
        nic = next((x for x in self.snapshot.network_details if x.name == self.table.selected_name()), None)
        if not nic:
            self.details.update_values({key: '—' for key in self.details.fields})
            for card in self.metrics:
                card.value.setText('—')
            return
        for card, value in zip(self.metrics, (rate(nic.download), rate(nic.upload), size(nic.received), size(nic.sent))):
            card.value.setText(value)
        self.details.update_values({'网卡': nic.name, '链路状态': '已连接' if nic.is_up else '未连接' if nic.is_up is not None else '不可读',
                                    'IPv4': '\n'.join(nic.ipv4) or '—', 'IPv6': '\n'.join(nic.ipv6) or '—', 'MAC': nic.mac,
                                    '链路速率': f'{nic.speed} Mbps' if nic.speed else '不可读或不适用', 'MTU': nic.mtu or '—',
                                    '收 / 发包数': f'{nic.packets_received:,} / {nic.packets_sent:,}',
                                    '错误 / 丢包': f'{nic.errors:,} / {nic.dropped:,}'})

    def update_snapshot(self, s):
        self.snapshot = s
        self.table.update_rows([(n.name, '已连接' if n.is_up else '未连接' if n.is_up is not None else '—',
                                 (rate(n.download), n.download if n.download is not None else -1),
                                 (rate(n.upload), n.upload if n.upload is not None else -1),
                                 (size(n.received), n.received), (size(n.sent), n.sent)) for n in s.network_details], s.network)
        self.trend.network = self.table.selected_name()
        self.trend.append(s)
        self.render_details()

    def set_theme(self):
        self.trend.set_theme()


class DiskPage(ScrollPage):
    def __init__(self, colors, header):
        super().__init__(header)
        self.snapshot = None
        self.colors = colors
        self.partition_widgets = {}
        self.body.addWidget(label('本地挂载分区', 'section'))
        self.partition_grid = QGridLayout()
        self.partition_grid.setSpacing(12)
        self.body.addLayout(self.partition_grid)
        self.body.addWidget(label('分区容量每 15 秒刷新；网络文件系统不扫描。可用容量可能扣除了文件系统保留空间。', 'muted', wrap=True))
        self.trend = TrendPanel(colors)
        self.trend.resource = 'disk'
        self.trend.setFixedHeight(270)
        self.body.addWidget(self.trend)
        self.body.addWidget(label('块设备实时 I/O · 点击设备切换曲线', 'section'))
        self.table = StatsTable(('设备', '读取', '写入', '读 IOPS', '写 IOPS', '繁忙度'), '磁盘设备 I/O 列表')
        self.table.currentCellChanged.connect(self.select_device)
        self.body.addWidget(self.table)
        self.note = label('IOPS 为每秒操作数。逻辑设备与物理设备可能记录同一次 I/O，不能直接相加。', 'muted', wrap=True)
        self.body.addWidget(self.note)
        self.body.addStretch(1)

    def select_device(self, *args):
        self.trend.disk_name = self.table.selected_name()
        self.trend.render()

    def update_snapshot(self, s):
        self.snapshot = s
        keys = [p.mountpoint for p in s.partitions]
        if list(self.partition_widgets) != keys:
            while self.partition_grid.count():
                self.partition_grid.takeAt(0).widget().deleteLater()
            self.partition_widgets = {}
            for index, part in enumerate(s.partitions):
                frame = panel()
                layout = vbox(frame)
                title = label(part.mountpoint, 'section', wrap=True)
                device = label(f'{part.device} · {part.filesystem}', 'muted', wrap=True)
                usage = label('—')
                bar = progress()
                free = label('—', 'muted')
                for widget in (title, device, usage, bar, free):
                    layout.addWidget(widget)
                self.partition_grid.addWidget(frame, index // 2, index % 2)
                self.partition_widgets[part.mountpoint] = (device, usage, bar, free)
        for part in s.partitions:
            device, usage, bar, free = self.partition_widgets[part.mountpoint]
            device.setText(f'{part.device} · {part.filesystem}')
            usage.setText(f'{size(part.used)} / {size(part.total)}  ·  {part.usage:.1f}%' if part.usage is not None else part.note)
            bar.setEnabled(part.usage is not None)
            bar.setValue(int(part.usage * 10) if part.usage is not None else 0)
            bar.setStyleSheet(f"QProgressBar::chunk {{background:{self.colors['danger' if (part.usage or 0) >= 90 else 'blue']};}}")
            free.setText(f'可用 {size(part.free)}' if part.usage is not None else '当前容量不可读')
        self.table.update_rows([(d.name, (optional_rate(d.read_rate), d.read_rate if d.read_rate is not None else -1),
                                 (optional_rate(d.write_rate), d.write_rate if d.write_rate is not None else -1),
                                 (f'{d.read_iops:.1f}' if d.read_iops is not None else '—', d.read_iops if d.read_iops is not None else -1),
                                 (f'{d.write_iops:.1f}' if d.write_iops is not None else '—', d.write_iops if d.write_iops is not None else -1),
                                 (f'{d.busy:.1f}%' if d.busy is not None else '—', d.busy if d.busy is not None else -1)) for d in s.disks])
        self.trend.disk_name = self.table.selected_name()
        self.trend.append(s)
        self.note.setText('IOPS 为每秒操作数。逻辑设备与物理设备可能记录同一次 I/O，不能直接相加。' if s.disks else '当前环境没有可读的块设备 I/O 计数。')

    def set_theme(self):
        self.trend.set_theme()
        if self.snapshot:
            for part in self.snapshot.partitions:
                bar = self.partition_widgets[part.mountpoint][2]
                bar.setStyleSheet(f"QProgressBar::chunk {{background:{self.colors['danger' if (part.usage or 0) >= 90 else 'blue']};}}")
