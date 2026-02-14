"""Specified-dates TOML editor -- GUI window for specified-dates.toml.

Uses src/io/specified_days_loader and specified_days_writer for IO.
GUI class (SpecifiedDatesEditorWindow) requires PySide6.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.common.base_editor import BaseEditorWindow
from src.gui.editors.workers_editor import load_hospital_choices
from src.io.specified_days_loader import load_specified_days
from src.io.specified_days_writer import dump_specified_days


# ---------------------------------------------------------------------------
# Pure logic helpers
# ---------------------------------------------------------------------------
def get_default_month(today: date) -> tuple[int, int]:
    """Return (year, month) for the next month relative to *today*."""
    if today.month == 12:
        return (today.year + 1, 1)
    return (today.year, today.month + 1)


def get_addable_hospitals(known: list[str], already_added: set[str]) -> list[str]:
    """Return hospitals from *known* that are not yet in *already_added*."""
    return [h for h in known if h not in already_added]


def is_in_displayed_month(
    cell_year: int,
    cell_month: int,
    display_year: int,
    display_month: int,
) -> bool:
    """Return True if the cell belongs to the displayed month."""
    return cell_year == display_year and cell_month == display_month


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

    def paintCell(self, painter: QPainter, rect: QRect, qdate: QDate) -> None:
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
class SpecifiedDatesEditorWindow(BaseEditorWindow):
    """specified-dates.toml GUI editor -- hospital list + calendar."""

    _file_filter = "TOML (*.toml)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Specified Dates Editor")
        self.resize(900, 600)
        self._model: dict[str, set[int]] = {}
        self._hospitals_path: Path | None = None

        # -- left: hospital list --
        self.list_hosp = QListWidget()
        self.list_hosp.currentRowChanged.connect(self._on_select_hospital)

        btn_add = QPushButton("\u75c5\u9662\u8ffd\u52a0")
        btn_del = QPushButton("\u75c5\u9662\u524a\u9664")
        btn_add.clicked.connect(self._add_hospital)
        btn_del.clicked.connect(self._del_hospital)

        btn_up = QPushButton("\u2191 \u4e0a\u3078")
        btn_down = QPushButton("\u2193 \u4e0b\u3078")
        btn_up.clicked.connect(self._move_hospital_up)
        btn_down.clicked.connect(self._move_hospital_down)

        crud_btns = QHBoxLayout()
        crud_btns.addWidget(btn_add)
        crud_btns.addWidget(btn_del)

        move_btns = QHBoxLayout()
        move_btns.addWidget(btn_up)
        move_btns.addWidget(btn_down)
        move_btns.addStretch(1)

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
        left.addLayout(move_btns)
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
            raw = load_specified_days(str(path))
            self._model = {name: set(days) for name, days in raw.items()}
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

    def set_hospitals_path(self, path: Path) -> None:
        """Set the path to hospitals.toml for hospital name choices."""
        self._hospitals_path = path

    def save_to(self, path: Path) -> None:
        """Write model to a TOML file."""
        data = {name: sorted(days) for name, days in self._model.items()}
        dump_specified_days(data, str(path))
        self.current_path = path
        self.setWindowTitle(f"Specified Dates Editor \u2014 {path.name}")

    # -- list refresh --
    def _refresh_hospital_list(self) -> None:
        self.list_hosp.clear()
        for name in self._model:
            self.list_hosp.addItem(QListWidgetItem(name))
        if self.list_hosp.count() > 0 and self.list_hosp.currentRow() < 0:
            self.list_hosp.setCurrentRow(0)
        else:
            self._on_select_hospital(self.list_hosp.currentRow())

    def _current_hospital_name(self) -> str | None:
        item = self.list_hosp.currentItem()
        if item is None:
            return None
        name = item.text()
        if name not in self._model:
            return None
        return name

    def _on_select_hospital(self, _row: int) -> None:
        self._update_calendar_formats()

    # -- CRUD --
    def _add_hospital(self) -> None:
        known: list[str] = []
        if self._hospitals_path is not None:
            known = load_hospital_choices(self._hospitals_path)
        choices = get_addable_hospitals(known, set(self._model.keys()))
        if not choices:
            QMessageBox.information(
                self,
                "\u60c5\u5831",
                "\u8ffd\u52a0\u53ef\u80fd\u306a\u75c5\u9662\u304c\u3042\u308a\u307e\u305b\u3093\u3002",
            )
            return
        name, ok = QInputDialog.getItem(
            self, "\u75c5\u9662\u8ffd\u52a0", "\u75c5\u9662\u540d:", choices, editable=False
        )
        if not ok or not name:
            return
        if name in self._model:
            return
        self._model[name] = set()
        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(len(self._model) - 1)

    def _del_hospital(self) -> None:
        name = self._current_hospital_name()
        if name is None:
            return
        row = self.list_hosp.currentRow()
        ret = QMessageBox.question(
            self,
            "\u78ba\u8a8d",
            f"'{name}' \u3092\u524a\u9664\u3057\u307e\u3059\u304b?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        del self._model[name]
        self._refresh_hospital_list()
        if self._model:
            self.list_hosp.setCurrentRow(min(row, len(self._model) - 1))
        else:
            self._update_calendar_formats()

    # -- move --
    def _swap_hospitals(self, i: int, j: int) -> None:
        keys = list(self._model.keys())
        if i < 0 or j < 0 or i >= len(keys) or j >= len(keys):
            return
        keys[i], keys[j] = keys[j], keys[i]
        self._model = {k: self._model[k] for k in keys}
        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(j)

    def _move_hospital_up(self) -> None:
        row = self.list_hosp.currentRow()
        if row > 0:
            self._swap_hospitals(row, row - 1)

    def _move_hospital_down(self) -> None:
        row = self.list_hosp.currentRow()
        if 0 <= row < len(self._model) - 1:
            self._swap_hospitals(row, row + 1)

    # -- calendar --
    def _on_date_clicked(self, date: QDate) -> None:
        name = self._current_hospital_name()
        if name is None:
            return
        y = self._calendar.yearShown()
        m = self._calendar.monthShown()
        if date.year() != y or date.month() != m:
            return
        day = date.day()
        dates = self._model[name]
        if day in dates:
            dates.remove(day)
        else:
            dates.add(day)
        self._update_calendar_formats()

    def _on_page_changed(self, _year: int, _month: int) -> None:
        self._update_calendar_formats()

    def _update_calendar_formats(self) -> None:
        name = self._current_hospital_name()
        days = self._model[name] if name is not None else set()
        self._calendar.set_highlight_dates(days)
