"""Specified-dates TOML editor -- model/TOML conversion + GUI window.

Conversion functions (load/dump) are pure Python and GUI-independent.
GUI class (SpecifiedDatesEditorWindow) requires PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomlkit
from PySide6.QtCore import QDate
from PySide6.QtGui import QColor, QTextCharFormat
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

        btn_add = QPushButton("病院追加")
        btn_del = QPushButton("病院削除")
        btn_add.clicked.connect(self._add_hospital)
        btn_del.clicked.connect(self._del_hospital)

        crud_btns = QHBoxLayout()
        crud_btns.addWidget(btn_add)
        crud_btns.addWidget(btn_del)

        # -- right: calendar --
        self._calendar = QCalendarWidget()
        self._calendar.setGridVisible(True)
        self._calendar.clicked.connect(self._on_date_clicked)
        self._calendar.currentPageChanged.connect(self._on_page_changed)

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
        left.addWidget(QLabel("病院リスト"))
        left.addWidget(self.list_hosp)
        left.addLayout(crud_btns)

        right = QVBoxLayout()
        right.addWidget(QLabel("勤務日を選択してください"))
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
        except Exception as e:
            QMessageBox.critical(self, "\u30a8\u30e9\u30fc", f"読み込みに失敗:\n{e}")

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
        name, ok = QInputDialog.getText(self, "病院追加", "病院名:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if any(e.name == name for e in self._entries):
            QMessageBox.warning(self, "重複", "その病院名は既に存在します。")
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
            "確認",
            f"'{entry.name}' を削除しますか?",
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
        y = self._calendar.yearShown()
        m = self._calendar.monthShown()
        clear_fmt = QTextCharFormat()
        for d in range(1, 32):
            qd = QDate(y, m, d)
            if qd.isValid():
                self._calendar.setDateTextFormat(qd, clear_fmt)
        entry = self._current_entry()
        if entry is None:
            return
        sel_fmt = QTextCharFormat()
        sel_fmt.setBackground(QColor(255, 230, 160))
        sel_fmt.setFontWeight(700)
        for d in sorted(entry.dates):
            qd = QDate(y, m, d)
            if qd.isValid():
                self._calendar.setDateTextFormat(qd, sel_fmt)

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
        QMessageBox.information(self, "保存完了", f"{self.current_path.name} を保存しました。")

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "TOML (*.toml)")
        if path:
            self.save_to(Path(path))
            QMessageBox.information(self, "保存完了", f"{Path(path).name} を保存しました。")
