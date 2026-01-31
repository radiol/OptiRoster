from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import tomlkit
from PySide6.QtCore import QDate
from PySide6.QtGui import QAction, QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication,
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
    QToolBar,
    QVBoxLayout,
    QWidget,
)


@dataclass
class HospitalEntry:
    name: str
    dates: set[int] = field(default_factory=set)


def load_specified_dates(path: Path) -> list[HospitalEntry]:
    doc = tomlkit.parse(path.read_text(encoding="utf-8-sig"))
    hospitals = doc.get("hospitals", [])
    entries: list[HospitalEntry] = []
    for h in hospitals:
        name = str(h.get("name", "")).strip()
        dates_list = h.get("dates", [])
        dates_set = set(int(x) for x in dates_list)
        entries.append(HospitalEntry(name=name, dates=dates_set))
    return entries


def dump_specified_dates(entries: list[HospitalEntry]) -> str:
    doc = tomlkit.document()
    arr = tomlkit.aot()
    for e in entries:
        t = tomlkit.table()
        t.add("name", e.name)
        t.add("dates", sorted(e.dates))
        arr.append(t)
    doc.add("hospitals", arr)
    doc.add(tomlkit.nl())
    return tomlkit.dumps(doc)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("specified-dates.toml editor")

        self.current_path: Path | None = None
        self.entries: list[HospitalEntry] = []
        self.dirty = False

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.on_hospital_changed)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.clicked.connect(self.on_date_clicked)
        self.calendar.currentPageChanged.connect(self.on_calendar_page_changed)

        self.status_label = QLabel("No file loaded")

        add_btn = QPushButton("病院追加")
        add_btn.clicked.connect(self.add_hospital)

        del_btn = QPushButton("病院削除")
        del_btn.clicked.connect(self.remove_hospital)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("病院リスト"))
        left_layout.addWidget(self.list_widget)
        left_layout.addWidget(add_btn)
        left_layout.addWidget(del_btn)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("勤務日を選択してください"))
        right_layout.addWidget(self.calendar)
        right_layout.addWidget(self.status_label)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.addWidget(left, 1)
        layout.addWidget(right, 2)
        self.setCentralWidget(central)

        self._init_actions()

        self.update_calendar_formats()

    def _init_actions(self) -> None:
        tb = QToolBar("File")
        self.addToolBar(tb)

        act_open = QAction("開く", self)
        act_open.triggered.connect(self.open_file)
        tb.addAction(act_open)

        act_save = QAction("上書き保存", self)
        act_save.triggered.connect(self.save_file)
        tb.addAction(act_save)

        act_save_as = QAction("名前をつけて保存", self)
        act_save_as.triggered.connect(self.save_file_as)
        tb.addAction(act_save_as)

    def mark_dirty(self, value: bool) -> None:
        self.dirty = value
        title = "specified-dates.toml editor"
        if self.current_path:
            title += f" - {self.current_path.name}"
        if self.dirty:
            title += " *"
        self.setWindowTitle(title)

    def maybe_confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        ret = QMessageBox.question(
            self,
            "変更が保存されていません",
            "保存されていない変更があります。 変更を破棄して上書きしますか?",
            QMessageBox.Yes | QMessageBox.No,
        )
        return ret == QMessageBox.Yes

    def open_file(self) -> None:
        if not self.maybe_confirm_discard():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open specified-dates.toml",
            "",
            "TOML (*.toml);;All Files (*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        try:
            self.entries = load_specified_dates(path)
        except Exception as e:
            QMessageBox.critical(self, "Load error", f"Failed to load TOML:\n{e}")
            return

        self.current_path = path
        self.refresh_list()
        self.mark_dirty(False)
        self.status_label.setText(str(path))

        if self.entries:
            self.list_widget.setCurrentRow(0)
        else:
            self.update_calendar_formats()

    def save_file(self) -> None:
        if not self.current_path:
            self.save_file_as()
            return
        self._save_to_path(self.current_path)

    def save_file_as(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save specified-dates.toml",
            "specified-dates.toml",
            "TOML (*.toml);;All Files (*)",
        )
        if not file_path:
            return
        path = Path(file_path)
        self._save_to_path(path)
        self.current_path = path
        self.status_label.setText(str(path))

    def _save_to_path(self, path: Path) -> None:
        try:
            text = dump_specified_dates(self.entries)
            path.write_text(text, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Save error", f"Failed to save TOML:\n{e}")
            return
        self.mark_dirty(False)

    def refresh_list(self) -> None:
        self.list_widget.clear()
        for e in self.entries:
            item = QListWidgetItem(e.name)
            self.list_widget.addItem(item)

    def current_entry(self) -> HospitalEntry | None:
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.entries):
            return None
        return self.entries[row]

    def add_hospital(self) -> None:
        name, ok = QInputDialog.getText(self, "Add hospital", "Hospital name:")
        if not ok:
            return
        name = name.strip()
        if not name:
            return

        if any(e.name == name for e in self.entries):
            QMessageBox.warning(self, "Duplicate", "That hospital name already exists.")
            return

        self.entries.append(HospitalEntry(name=name))
        self.refresh_list()
        self.list_widget.setCurrentRow(len(self.entries) - 1)
        self.mark_dirty(True)

    def remove_hospital(self) -> None:
        row = self.list_widget.currentRow()
        e = self.current_entry()
        if e is None:
            return

        ret = QMessageBox.question(
            self,
            "Remove hospital",
            f"Remove '{e.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return

        del self.entries[row]
        self.refresh_list()
        self.mark_dirty(True)

        if self.entries:
            self.list_widget.setCurrentRow(min(row, len(self.entries) - 1))
        else:
            self.update_calendar_formats()

    def on_hospital_changed(self, _row: int) -> None:
        self.update_calendar_formats()

    def on_calendar_page_changed(self, _year: int, _month: int) -> None:
        self.update_calendar_formats()

    def on_date_clicked(self, date: QDate) -> None:
        e = self.current_entry()
        if e is None:
            return

        y = self.calendar.yearShown()
        m = self.calendar.monthShown()

        if date.year() != y or date.month() != m:
            return

        day = date.day()
        if day in e.dates:
            e.dates.remove(day)
        else:
            e.dates.add(day)

        self.mark_dirty(True)
        self.update_calendar_formats()

    def update_calendar_formats(self) -> None:
        # Note: QCalendarWidget keeps formats per date, so clear current month explicitly.
        y = self.calendar.yearShown()
        m = self.calendar.monthShown()

        # Clear all date formats for current month range
        # (1..31 safe; invalid QDate is ignored by widget)
        clear_fmt = QTextCharFormat()
        for d in range(1, 32):
            qd = QDate(y, m, d)
            if qd.isValid():
                self.calendar.setDateTextFormat(qd, clear_fmt)

        e = self.current_entry()
        if e is None:
            return

        # Highlight selected dates
        sel_fmt = QTextCharFormat()
        sel_fmt.setBackground(QColor(255, 230, 160))
        sel_fmt.setFontWeight(700)

        for d in sorted(e.dates):
            qd = QDate(y, m, d)
            if qd.isValid():
                self.calendar.setDateTextFormat(qd, sel_fmt)


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(900, 600)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
