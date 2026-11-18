"""Numeric sorting and search without per-cell QWidget allocation."""

import os

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyledItemDelegate

from .data import PortInfo, ProcessInfo, percent, size

SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class RecordModel(QAbstractTableModel):
    headers: tuple[str, ...] = ()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.headers[section]
        return None

    def set_rows(self, rows):
        # Normal ticks keep indexes and the user's scroll/selection intact.
        same_keys = [r.key for r in self.rows] == [r.key for r in rows]
        if not same_keys:
            self.beginResetModel()
        self.rows = list(rows)
        if not same_keys:
            self.endResetModel()
        elif self.rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.rows)-1, len(self.headers)-1))


class ProcessModel(RecordModel):
    headers = ("进程 / 中文用途", "CPU", "内存 RSS", "显存", "磁盘 I/O")

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row: ProcessInfo = self.rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (f"{row.name}   {row.pid}\n{row.description}",
                    percent(row.cpu) if row.cpu_available else "—",
                    size(row.rss), size(row.vram),
                    size(row.io_rate) + "/s" if row.io_rate is not None else "—")[column]
        if role == SORT_ROLE:
            return ((row.name.lower(), row.pid) if column == 0 else
                    [None, row.cpu, row.rss, row.vram, row.io_rate][column]
                    if [None, row.cpu, row.rss, row.vram, row.io_rate][column] is not None else -1)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{row.name} · PID {row.pid}\n{row.description}\n{row.command}"
        if role == Qt.ItemDataRole.ForegroundRole and column == 1 and (row.cpu or 0) >= 20:
            return QColor("#F3987E")
        if role == Qt.ItemDataRole.TextAlignmentRole and column > 0:
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        return None


class PortModel(RecordModel):
    headers = ("端口", "协议", "绑定地址", "所属进程", "PID")

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row: PortInfo = self.rows[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (str(row.port), row.protocol, row.address,
                    f"{row.name}\n{row.description}", str(row.pid) if row.pid else "受限")[column]
        if role == SORT_ROLE:
            return (row.port, row.protocol, row.address, row.name.lower(), row.pid or -1)[column]
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{row.endpoint} · {row.protocol}\n{row.description}"
        if role == Qt.ItemDataRole.TextAlignmentRole and column == 4:
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        return None


class RecordProxy(QSortFilterProxyModel):
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.query = ""
        self.scope = "all"
        self.protocol = "all"
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, source_row, source_parent):
        row = self.sourceModel().rows[source_row]
        if self.kind == "process":
            text = f"{row.name} {row.description} {row.pid} {row.command} {row.user}".casefold()
            if self.scope == "me" and row.uid != os.getuid():
                return False
            if self.scope == "gpu" and not (row.vram and row.vram > 0):
                return False
        else:
            text = f"{row.port} {row.address} {row.pid} {row.name} {row.description}".casefold()
            if self.scope != "all" and self.scope != row.scope:
                return False
            if self.protocol != "all" and self.protocol != row.protocol:
                return False
        query = self.query.casefold().strip()
        if query.startswith("pid:"):
            return str(row.pid) == query[4:].strip()
        return query in text

    def update_filter(self, *, query=None, scope=None, protocol=None):
        if query is not None:
            self.query = query
        if scope is not None:
            self.scope = scope
        if protocol is not None:
            self.protocol = protocol
        self.invalidateFilter()

    def lessThan(self, left, right):
        a = self.sourceModel().data(left, SORT_ROLE)
        b = self.sourceModel().data(right, SORT_ROLE)
        return a < b


class TwoLineDelegate(QStyledItemDelegate):
    """Render descriptions with a secondary color and elide long text."""

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.colors = colors

    def paint(self, painter, option, index):
        from PySide6.QtWidgets import QStyle, QStyleOptionViewItem
        from PySide6.QtGui import QFont, QFontMetrics
        text = index.data() or ""
        if "\n" not in text:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        top, bottom = text.split("\n", 1)
        rect = option.rect.adjusted(12, 5, -9, -5)
        painter.save()
        font = QFont(option.font)
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor(self.colors["text"]))
        painter.drawText(rect.adjusted(0, 0, 0, -rect.height()//2),
                         Qt.AlignmentFlag.AlignVCenter,
                         QFontMetrics(font).elidedText(top, Qt.TextElideMode.ElideRight, rect.width()))
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QColor(self.colors["muted"]))
        painter.drawText(rect.adjusted(0, rect.height()//2, 0, 0),
                         Qt.AlignmentFlag.AlignVCenter,
                         QFontMetrics(font).elidedText(bottom, Qt.TextElideMode.ElideRight, rect.width()))
        painter.restore()
