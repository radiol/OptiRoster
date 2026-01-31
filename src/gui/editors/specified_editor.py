"""Specified-dates TOML editor -- model/TOML conversion + GUI window.

Conversion functions (load/dump) are pure Python and GUI-independent.
GUI class (SpecifiedDatesEditorWindow) requires PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import tomlkit
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCalendarWidget,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from tomlkit import aot, document, parse, table


# ---------------------------------------------------------------------------
# Model (dataclass)
# ---------------------------------------------------------------------------
@dataclass
class HospitalEntry:
    name: str
    dates: set[int] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Pure logic helpers
# ---------------------------------------------------------------------------
def get_default_month(today: date) -> tuple[int, int]:
    """Return (year, month) for the next month relative to *today*."""
    if today.month == 12:
        return (today.year + 1, 1)
    return (today.year, today.month + 1)


def is_in_displayed_month(
    cell_year: int,
    cell_month: int,
    display_year: int,
    display_month: int,
) -> bool:
    """Return True if the cell belongs to the displayed month."""
    return cell_year == display_year and cell_month == display_month


# ---------------------------------------------------------------------------
# tomlkit document helpers
# ---------------------------------------------------------------------------
def _ensure_hospitals(doc: tomlkit.TOMLDocument) -> tomlkit.items.AoT:
    """doc 内に hospitals AoT がなければ作り、返す."""
    if "hospitals" not in doc:
        doc["hospitals"] = aot()
    return doc["hospitals"]


def _entry_tbl_to_model(h: tomlkit.items.Table) -> HospitalEntry:
    """tomlkit table -> HospitalEntry dataclass."""
    name = str(h.get("name", "")).strip()
    dates_list = h.get("dates", [])
    dates_set = {int(x) for x in dates_list}
    return HospitalEntry(name=name, dates=dates_set)


def _apply_model_to_entry_tbl(
    tbl: tomlkit.items.Table,
    model: HospitalEntry,
) -> None:
    """HospitalEntry dataclass -> tomlkit table (in-place update)."""
    tbl["name"] = model.name
    tbl["dates"] = sorted(model.dates)


# ---------------------------------------------------------------------------
# Public file-level IO
# ---------------------------------------------------------------------------
def load_specified_dates(path: Path) -> list[HospitalEntry]:
    """TOML file -> list[HospitalEntry]."""
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    doc = parse(text)
    return [_entry_tbl_to_model(h) for h in doc.get("hospitals", [])]


def dump_specified_dates(entries: list[HospitalEntry], path: Path) -> None:
    """list[HospitalEntry] -> TOML file."""
    doc = document()
    hospitals_aot = aot()
    for e in entries:
        tbl = table()
        _apply_model_to_entry_tbl(tbl, e)
        hospitals_aot.append(tbl)
    doc["hospitals"] = hospitals_aot
    path.write_text(doc.as_string(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Calendar widget (paintCell override, hides other-month dates)
# ---------------------------------------------------------------------------
_HIGHLIGHT_BG = QColor(255, 230, 160)
_HIGHLIGHT_BORDER = QColor(200, 170, 80)
_NORMAL_BG = QColor(255, 255, 255)
_BLANK_BG = QColor(245, 245, 245)

_CALENDAR_QSS = """\
QCalendarWidget QAbstractItemView {
    selection-background-color: transparent;
    selection-color: black;
}
QCalendarWidget QAbstractItemView::item:hover {
    background-color: transparent;
    color: black;
}
QCalendarWidget QAbstractItemView::item:focus {
    background-color: transparent;
    color: black;
}
"""


class _MonthCalendar(QCalendarWidget):
    """QCalendarWidget subclass: hides other-month dates, custom highlight."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._highlight_days: set[int] = set()
        self.setStyleSheet(_CALENDAR_QSS)

    def set_highlight_dates(self, days: set[int]) -> None:
        """Set highlighted day numbers and repaint."""
        self._highlight_days = set(days)
        self.updateCells()

    def navigate_to(self, year: int, month: int) -> None:
        """Programmatically switch the displayed page."""
        self.setCurrentPage(year, month)

    def paintCell(self, painter: QPainter, rect, qdate: QDate) -> None:
        """Custom cell rendering: blank other-month, yellow highlight."""
        painter.save()
        y = self.yearShown()
        m = self.monthShown()

        if not is_in_displayed_month(qdate.year(), qdate.month(), y, m):
            # Blank cell for other-month dates
            painter.fillRect(rect, _BLANK_BG)
        elif qdate.day() in self._highlight_days:
            # Highlighted date -- yellow bg + border + bold
            painter.fillRect(rect, _HIGHLIGHT_BG)
            pen = QPen(_HIGHLIGHT_BORDER)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(qdate.day()))
        else:
            # Normal date in current month
            painter.fillRect(rect, _NORMAL_BG)
            painter.setPen(Qt.GlobalColor.black)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(qdate.day()))

        painter.restore()


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class SpecifiedDatesEditorWindow(QMainWindow):
    """specified-dates.toml GUI editor -- hospital list + calendar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Specified Dates Editor")
        self.resize(900, 600)
        self.current_path: Path | None = None
        self._entries: list[HospitalEntry] = []

        # -- left: hospital list --
        self.list_hosp = QListWidget()
        self.list_hosp.currentRowChanged.connect(self._on_select_hospital)

        btn_add = QPushButton("\u75c5\u9662\u8ffd\u52a0")
        btn_del = QPushButton("\u75c5\u9662\u524a\u9664")
        btn_add.clicked.connect(self._add_hospital)
        btn_del.clicked.connect(self._del_hospital)

        crud_btns = QHBoxLayout()
        crud_btns.addWidget(btn_add)
        crud_btns.addWidget(btn_del)

        # -- right: calendar (default to next month) --
        self._calendar = _MonthCalendar()
        self._calendar.setGridVisible(True)
        self._calendar.clicked.connect(self._on_date_clicked)
        self._calendar.currentPageChanged.connect(self._on_page_changed)

        y, m = get_default_month(date.today())
        self._calendar.navigate_to(y, m)

        self._status_label = QLabel("No file loaded")

        # -- toolbar --
        btn_open = QPushButton("Open")
        btn_save = QPushButton("Save")
        btn_save_as = QPushButton("Save As")
        btn_open.clicked.connect(self._on_open)
        btn_save.clicked.connect(self._on_save)
        btn_save_as.clicked.connect(self._on_save_as)

        file_btns = QHBoxLayout()
        file_btns.addWidget(btn_open)
        file_btns.addWidget(btn_save)
        file_btns.addWidget(btn_save_as)

        # -- layout --
        left = QVBoxLayout()
        left.addWidget(QLabel("File"))
        left.addLayout(file_btns)
        left.addSpacing(6)
        left.addWidget(QLabel("\u75c5\u9662\u30ea\u30b9\u30c8"))
        left.addWidget(self.list_hosp)
        left.addLayout(crud_btns)

        right = QVBoxLayout()
        right.addWidget(
            QLabel("\u52e4\u52d9\u65e5\u3092\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044")
        )
        right.addWidget(self._calendar)
        right.addWidget(self._status_label)

        root = QHBoxLayout()
        root.addLayout(left, 1)
        root.addLayout(right, 2)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._update_calendar_formats()

    # -- public API --
    def open_path(self, path: Path) -> None:
        """Load a TOML file and refresh the UI."""
        try:
            self._entries = load_specified_dates(path)
            self.current_path = path
            self.setWindowTitle(f"Specified Dates Editor \u2014 {path.name}")
            self._refresh_hospital_list()
            self._status_label.setText(str(path))
            y, m = get_default_month(date.today())
            self._calendar.navigate_to(y, m)
        except Exception as e:
            QMessageBox.critical(
                self, "\u30a8\u30e9\u30fc", f"\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557:\n{e}"
            )

    def save_to(self, path: Path) -> None:
        """Write entries to a TOML file."""
        dump_specified_dates(self._entries, path)
        self.current_path = path
        self.setWindowTitle(f"Specified Dates Editor \u2014 {path.name}")

    # -- list refresh --
    def _refresh_hospital_list(self) -> None:
        self.list_hosp.clear()
        for e in self._entries:
            self.list_hosp.addItem(QListWidgetItem(e.name))
        if self.list_hosp.count() > 0 and self.list_hosp.currentRow() < 0:
            self.list_hosp.setCurrentRow(0)
        else:
            self._on_select_hospital(self.list_hosp.currentRow())

    def _current_entry(self) -> HospitalEntry | None:
        row = self.list_hosp.currentRow()
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _on_select_hospital(self, _row: int) -> None:
        self._update_calendar_formats()

    # -- CRUD --
    def _add_hospital(self) -> None:
        name, ok = QInputDialog.getText(self, "\u75c5\u9662\u8ffd\u52a0", "\u75c5\u9662\u540d:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if any(e.name == name for e in self._entries):
            QMessageBox.warning(
                self,
                "\u91cd\u8907",
                "\u305d\u306e\u75c5\u9662\u540d\u306f\u65e2\u306b\u5b58\u5728\u3057\u307e\u3059\u3002",
            )
            return
        self._entries.append(HospitalEntry(name=name))
        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(len(self._entries) - 1)

    def _del_hospital(self) -> None:
        row = self.list_hosp.currentRow()
        entry = self._current_entry()
        if entry is None:
            return
        ret = QMessageBox.question(
            self,
            "\u78ba\u8a8d",
            f"'{entry.name}' \u3092\u524a\u9664\u3057\u307e\u3059\u304b?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        del self._entries[row]
        self._refresh_hospital_list()
        if self._entries:
            self.list_hosp.setCurrentRow(min(row, len(self._entries) - 1))
        else:
            self._update_calendar_formats()

    # -- calendar --
    def _on_date_clicked(self, date: QDate) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        y = self._calendar.yearShown()
        m = self._calendar.monthShown()
        if date.year() != y or date.month() != m:
            return
        day = date.day()
        if day in entry.dates:
            entry.dates.remove(day)
        else:
            entry.dates.add(day)
        self._update_calendar_formats()

    def _on_page_changed(self, _year: int, _month: int) -> None:
        self._update_calendar_formats()

    def _update_calendar_formats(self) -> None:
        entry = self._current_entry()
        days = entry.dates if entry is not None else set()
        self._calendar.set_highlight_dates(days)

    # -- file operations --
    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open TOML", "", "TOML (*.toml)")
        if path:
            self.open_path(Path(path))

    def _on_save(self) -> None:
        if self.current_path is None:
            self._on_save_as()
            return
        self.save_to(self.current_path)
        QMessageBox.information(
            self,
            "\u4fdd\u5b58\u5b8c\u4e86",
            f"{self.current_path.name} \u3092\u4fdd\u5b58\u3057\u307e\u3057\u305f\u3002",
        )

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "TOML (*.toml)")
        if path:
            self.save_to(Path(path))
            QMessageBox.information(
                self,
                "\u4fdd\u5b58\u5b8c\u4e86",
                f"{Path(path).name} \u3092\u4fdd\u5b58\u3057\u307e\u3057\u305f\u3002",
            )
