"""Shared palette for Qt, Fluent widgets, and plotted data."""

DARK = dict(bg="#17191E", sidebar="#1C1E24", surface="#20232A", raised="#292C34",
            line="#30333C", text="#F1F0F3", muted="#A2A6B2", subtle="#828897",
            accent="#F3987E", accent_bg="#3B2C2B", green="#7ED5B6", purple="#B1A0F2",
            blue="#84B5EF", danger="#F28C95")
LIGHT = dict(bg="#F5F5F7", sidebar="#EFEFF2", surface="#FFFFFF", raised="#E7E8ED",
             line="#DEDFE6", text="#262831", muted="#626875", subtle="#747987",
             accent="#AE4B32", accent_bg="#F8E8E2", green="#267B60", purple="#7660B5",
             blue="#3C70AE", danger="#B34D5B")


def stylesheet(c):
    return """
QMainWindow, QWidget#AppRoot { background: %(bg)s; color: %(text)s; }
QWidget { color: %(text)s; font-family: "Noto Sans CJK SC", "Ubuntu", "DejaVu Sans"; font-size: 12px; }
QLabel { background: transparent; border: none; }
QLabel[role="muted"] { color: %(muted)s; font-size: 11px; }
QLabel[role="eyebrow"] { color: %(subtle)s; font-size: 9px; }
QLabel[role="title"] { font-size: 25px; font-weight: 600; }
QLabel[role="section"] { font-size: 13px; font-weight: 600; }
QLabel[role="value"] { font-size: 26px; font-weight: 600; }
QLabel[role="purpose"] { color: %(accent)s; font-size: 11px; }
QLabel[role="badge"] { color: %(green)s; background: %(raised)s; border-radius: 5px; padding: 4px 7px; font-size: 10px; }
QFrame[role="card"] { background: %(surface)s; border: 1px solid %(line)s; border-radius: 13px; }
QFrame[role="card"][selected="true"] { border-color: %(accent)s; background: %(accent_bg)s; }
QFrame#Sidebar { background: %(sidebar)s; border-right: 1px solid %(line)s; }
QPushButton[variant="nav"] { background: transparent; border: 1px solid transparent; border-radius: 9px; color: %(muted)s; padding: 11px 12px; text-align: left; }
QPushButton[variant="nav"]:hover { background: %(raised)s; color: %(text)s; }
QPushButton[variant="nav"]:checked { background: %(accent_bg)s; color: %(accent)s; border-color: %(accent_bg)s; }
QPushButton[variant="nav"]:focus { border-color: %(accent)s; }
QPushButton[variant="segment"] { background: transparent; border: 1px solid %(line)s; border-radius: 6px; color: %(muted)s; padding: 4px 8px; font-size: 10px; }
QPushButton[variant="segment"]:checked { color: %(accent)s; background: %(accent_bg)s; border-color: %(accent)s; }
QStatusBar { color: %(muted)s; background: %(sidebar)s; border-top: 1px solid %(line)s; font-size: 10px; }
QStatusBar::item { border: none; }
QTableView { background: %(surface)s; color: %(text)s; border: none; gridline-color: %(line)s; selection-background-color: %(accent_bg)s; selection-color: %(text)s; outline: none; }
QTableView::item { border: none; border-bottom: 1px solid %(line)s; padding: 8px; }
QTableView::item:hover { background: %(raised)s; }
QTableView::item:selected { background: %(accent_bg)s; }
QHeaderView { background: %(surface)s; }
QHeaderView::section { color: %(muted)s; background: %(surface)s; border: none; border-bottom: 1px solid %(line)s; padding: 11px 8px; font-size: 10px; }
QTableCornerButton::section { background: %(surface)s; border: none; }
QProgressBar { border: none; border-radius: 3px; background: %(raised)s; height: 5px; min-height: 5px; max-height: 5px; color: transparent; }
QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
QScrollBar::handle:vertical { background: %(subtle)s; border-radius: 3px; min-height: 25px; }
QScrollBar:horizontal { background: transparent; height: 6px; }
QScrollBar::handle:horizontal { background: %(subtle)s; border-radius: 3px; min-width: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QPlainTextEdit[role="command"] { background: %(bg)s; border: 1px solid %(line)s; border-radius: 8px; padding: 7px; color: %(text)s; font-family: "DejaVu Sans Mono"; font-size: 10px; }
QToolTip { background: %(raised)s; border: 1px solid %(line)s; color: %(text)s; padding: 7px; }
QDialog { background: %(surface)s; }
QMenu { background: %(surface)s; border: 1px solid %(line)s; padding: 5px; }
QMenu::item { padding: 7px 18px; color: %(text)s; }
QMenu::item:selected { background: %(accent_bg)s; }
""" % c
