import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from tomlkit import aot, document, parse, table

SHIFT_TYPES = ["AM", "PM", "日勤", "当直"]
FREQUENCIES = ["毎週", "隔週", "指定日"]
WEEKDAYS = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]


@dataclass
class ShiftModel:
    shift_type: str
    weekdays: list[str]
    frequency: str


@dataclass
class HospitalModel:
    name: str
    is_remote: bool
    is_university: bool
    shifts: list[ShiftModel]


def _ensure_hospitals(doc):
    if "hospitals" not in doc:
        doc["hospitals"] = aot()
    return doc["hospitals"]


def _ensure_shifts(hosp_tbl):
    if "shifts" not in hosp_tbl:
        hosp_tbl["shifts"] = aot()
    return hosp_tbl["shifts"]


def _hosp_tbl_to_model(h) -> HospitalModel:
    shifts = []
    if "shifts" in h and h["shifts"] is not None:
        shifts.extend(
            ShiftModel(
                shift_type=str(s.get("shift_type", "")),
                weekdays=[str(x) for x in (s.get("weekdays", []) or [])],
                frequency=str(s.get("frequency", "")),
            )
            for s in h["shifts"]
        )
    return HospitalModel(
        name=str(h.get("name", "")),
        is_remote=bool(h.get("is_remote", False)),
        is_university=bool(h.get("is_university", False)),
        shifts=shifts,
    )


def _apply_model_to_hosp_tbl(hosp_tbl, model: HospitalModel):
    hosp_tbl["name"] = model.name
    hosp_tbl["is_remote"] = bool(model.is_remote)
    hosp_tbl["is_university"] = bool(model.is_university)

    shifts_aot = _ensure_shifts(hosp_tbl)
    while len(shifts_aot) > 0:
        shifts_aot.pop()

    for sm in model.shifts:
        st = table()
        st["shift_type"] = sm.shift_type
        st["weekdays"] = sm.weekdays
        st["frequency"] = sm.frequency
        shifts_aot.append(st)


class ShiftDialog(QDialog):
    def __init__(self, parent=None, initial: ShiftModel | None = None):
        super().__init__(parent)
        self.setWindowTitle("シフト編集")

        self.combo_type = QComboBox()
        self.combo_type.addItems(SHIFT_TYPES)

        self.combo_freq = QComboBox()
        self.combo_freq.addItems(FREQUENCIES)

        self.week_checks = []
        week_box = QGroupBox("Weekdays")
        grid = QGridLayout()
        for i, wd in enumerate(WEEKDAYS):
            cb = QCheckBox(wd)
            self.week_checks.append(cb)
            grid.addWidget(cb, i // 4, i % 4)
        week_box.setLayout(grid)

        form = QFormLayout()
        form.addRow("shift_type", self.combo_type)
        form.addRow("frequency", self.combo_freq)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self._validate_then_accept)
        btn_cancel.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addWidget(week_box)
        root.addLayout(btns)
        self.setLayout(root)

        if initial:
            if initial.shift_type in SHIFT_TYPES:
                self.combo_type.setCurrentText(initial.shift_type)
            if initial.frequency in FREQUENCIES:
                self.combo_freq.setCurrentText(initial.frequency)
            wset = set(initial.weekdays)
            for cb in self.week_checks:
                cb.setChecked(cb.text() in wset)

    def get_model(self) -> ShiftModel:
        weekdays = [cb.text() for cb in self.week_checks if cb.isChecked()]
        return ShiftModel(
            shift_type=self.combo_type.currentText(),
            weekdays=weekdays,
            frequency=self.combo_freq.currentText(),
        )

    def _validate_then_accept(self):
        weekdays = [cb.text() for cb in self.week_checks if cb.isChecked()]
        if not weekdays:
            QMessageBox.warning(self, "Error", "Weekdaysは1つ以上選択してください。")
            return
        self.accept()


class HospitalDialog(QDialog):
    def __init__(self, parent=None, initial: HospitalModel | None = None):
        super().__init__(parent)
        self.setWindowTitle("病院編集")

        self.edit_name = QLineEdit()
        self.chk_remote = QCheckBox("遠隔地か?")
        self.chk_univ = QCheckBox("大学病院か?")

        self.shift_table = QTableWidget(0, 3)
        self.shift_table.setHorizontalHeaderLabels(["shift_type", "weekdays", "frequency"])
        self.shift_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.shift_table.setSelectionMode(QTableWidget.SingleSelection)
        self.shift_table.horizontalHeader().setStretchLastSection(True)

        btn_shift_add = QPushButton("シフト新規追加")
        btn_shift_edit = QPushButton("シフト編集")
        btn_shift_del = QPushButton("シフト削除")

        btn_shift_add.clicked.connect(self._add_shift)
        btn_shift_edit.clicked.connect(self._edit_shift)
        btn_shift_del.clicked.connect(self._del_shift)

        shift_btns = QHBoxLayout()
        shift_btns.addWidget(btn_shift_add)
        shift_btns.addWidget(btn_shift_edit)
        shift_btns.addWidget(btn_shift_del)
        shift_btns.addStretch(1)

        form = QFormLayout()
        form.addRow("name", self.edit_name)
        form.addRow("", self.chk_remote)
        form.addRow("", self.chk_univ)

        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        btn_ok.clicked.connect(self._validate_then_accept)
        btn_cancel.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addWidget(QLabel("Shift list"))
        root.addWidget(self.shift_table)
        root.addLayout(shift_btns)
        root.addLayout(btns)
        self.setLayout(root)

        if initial:
            self.edit_name.setText(initial.name)
            self.chk_remote.setChecked(initial.is_remote)
            self.chk_univ.setChecked(initial.is_university)
            for s in initial.shifts:
                self._append_shift_row(s)

    def _append_shift_row(self, s: ShiftModel):
        r = self.shift_table.rowCount()
        self.shift_table.insertRow(r)
        self.shift_table.setItem(r, 0, QTableWidgetItem(s.shift_type))
        self.shift_table.setItem(r, 1, QTableWidgetItem(",".join(s.weekdays)))
        self.shift_table.setItem(r, 2, QTableWidgetItem(s.frequency))

    def _row_to_shift(self, row: int) -> ShiftModel:
        stype = self.shift_table.item(row, 0).text() if self.shift_table.item(row, 0) else ""
        wds = self.shift_table.item(row, 1).text() if self.shift_table.item(row, 1) else ""
        freq = self.shift_table.item(row, 2).text() if self.shift_table.item(row, 2) else ""
        weekdays = [x for x in wds.split(",") if x]
        return ShiftModel(shift_type=stype, weekdays=weekdays, frequency=freq)

    def _selected_row(self) -> int | None:
        items = self.shift_table.selectedItems()
        if not items:
            return None
        return items[0].row()

    def _add_shift(self):
        dlg = ShiftDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._append_shift_row(dlg.get_model())

    def _edit_shift(self):
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "編集するシフトを選択してください。")
            return
        current = self._row_to_shift(row)
        dlg = ShiftDialog(self, current)
        if dlg.exec() == QDialog.Accepted:
            m = dlg.get_model()
            self.shift_table.item(row, 0).setText(m.shift_type)
            self.shift_table.item(row, 1).setText(",".join(m.weekdays))
            self.shift_table.item(row, 2).setText(m.frequency)

    def _del_shift(self):
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "削除するシフトを選択してください。")
            return
        self.shift_table.removeRow(row)

    def _validate_then_accept(self):
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "病院名(name)は必須です。")
            return

        for r in range(self.shift_table.rowCount()):
            stype = self.shift_table.item(r, 0).text().strip()
            freq = self.shift_table.item(r, 2).text().strip()
            if stype not in SHIFT_TYPES:
                QMessageBox.warning(self, "Error", f"shift_typeが不正です: row={r + 1}")
                return
            if freq not in FREQUENCIES:
                QMessageBox.warning(self, "Error", f"frequencyが不正です: row={r + 1}")
                return
        self.accept()

    def get_model(self) -> HospitalModel:
        shifts = [self._row_to_shift(r) for r in range(self.shift_table.rowCount())]
        return HospitalModel(
            name=self.edit_name.text().strip(),
            is_remote=self.chk_remote.isChecked(),
            is_university=self.chk_univ.isChecked(),
            shifts=shifts,
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TOML Hospitals Editor")

        self.doc = document()
        self.current_path: Path | None = None

        self.list_hosp = QListWidget()
        self.list_hosp.currentRowChanged.connect(self._on_select_hospital)
        self.list_hosp.itemDoubleClicked.connect(self._on_hospital_double_clicked)

        self.lbl_name = QLabel("-")
        self.lbl_flags = QLabel("-")

        self.shift_table = QTableWidget(0, 3)
        self.shift_table.setHorizontalHeaderLabels(["shift_type", "weekdays", "frequency"])
        self.shift_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.shift_table.setSelectionMode(QTableWidget.SingleSelection)
        self.shift_table.horizontalHeader().setStretchLastSection(True)

        btn_open = QPushButton("Open...")
        btn_save = QPushButton("上書き保存")
        btn_save_as = QPushButton("名前をつけて保存")

        btn_open.clicked.connect(self._open_file)
        btn_save.clicked.connect(self._save_file)
        btn_save_as.clicked.connect(self._save_file_as)

        file_btns = QHBoxLayout()
        file_btns.addWidget(btn_open)
        file_btns.addWidget(btn_save)
        file_btns.addWidget(btn_save_as)

        btn_up = QPushButton("↑ 上へ")
        btn_down = QPushButton("↓ 下へ")

        btn_up.clicked.connect(self._move_hospital_up)
        btn_down.clicked.connect(self._move_hospital_down)

        move_btns = QHBoxLayout()
        move_btns.addWidget(btn_up)
        move_btns.addWidget(btn_down)
        move_btns.addStretch(1)

        btn_add = QPushButton("病院 新規追加")
        btn_edit = QPushButton("病院 編集")
        btn_del = QPushButton("病院 削除")

        btn_add.clicked.connect(self._add_hospital)
        btn_edit.clicked.connect(self._edit_hospital)
        btn_del.clicked.connect(self._del_hospital)

        left_btns = QHBoxLayout()
        left_btns.addWidget(btn_add)
        left_btns.addWidget(btn_edit)
        left_btns.addWidget(btn_del)

        left = QVBoxLayout()
        left.addWidget(QLabel("File"))
        left.addLayout(file_btns)
        left.addSpacing(6)
        left.addWidget(QLabel("Hospitals"))
        left.addWidget(self.list_hosp)
        left.addLayout(move_btns)
        left.addLayout(left_btns)

        right = QVBoxLayout()
        right.addWidget(QLabel("Selected hospital"))
        right.addWidget(self.lbl_name)
        right.addWidget(self.lbl_flags)
        right.addSpacing(8)
        right.addWidget(QLabel("Shifts"))
        right.addWidget(self.shift_table)

        root = QHBoxLayout()
        root.addLayout(left, 2)
        root.addLayout(right, 3)

        w = QWidget()
        w.setLayout(root)
        self.setCentralWidget(w)

        self._build_menu()
        self._refresh_hospital_list()

    def load_toml(self, path: Path):
        text = path.read_text(encoding="utf-8")
        self.doc = parse(text)
        self.current_path = path
        _ensure_hospitals(self.doc)
        self._refresh_hospital_list()
        self.statusBar().showMessage(f"Opened: {path}")

    def _build_menu(self):
        m_file = self.menuBar().addMenu("File")

        act_open = m_file.addAction("Open...")
        act_save = m_file.addAction("Save")
        act_save_as = m_file.addAction("Save As...")

        act_open.triggered.connect(self._open_file)
        act_save.triggered.connect(self._save_file)
        act_save_as.triggered.connect(self._save_file_as)

    def _hospitals(self):
        return _ensure_hospitals(self.doc)

    def _refresh_hospital_list(self):
        self.list_hosp.clear()
        for h in self._hospitals():
            name = str(h.get("name", ""))
            item = QListWidgetItem(name)
            self.list_hosp.addItem(item)

        if self.list_hosp.count() > 0 and self.list_hosp.currentRow() < 0:
            self.list_hosp.setCurrentRow(0)
        else:
            self._on_select_hospital(self.list_hosp.currentRow())

    def _on_hospital_double_clicked(self, _item):
        # Open edit dialog for the currently selected hospital
        self._edit_hospital()

    def _on_select_hospital(self, row: int):
        self.shift_table.setRowCount(0)

        if row < 0 or row >= len(self._hospitals()):
            self.lbl_name.setText("-")
            self.lbl_flags.setText("-")
            return

        h = self._hospitals()[row]
        m = _hosp_tbl_to_model(h)

        self.lbl_name.setText(f"name: {m.name}")
        self.lbl_flags.setText(f"is_remote: {m.is_remote}   is_university: {m.is_university}")

        for s in m.shifts:
            r = self.shift_table.rowCount()
            self.shift_table.insertRow(r)
            self.shift_table.setItem(r, 0, QTableWidgetItem(s.shift_type))
            self.shift_table.setItem(r, 1, QTableWidgetItem(",".join(s.weekdays)))
            self.shift_table.setItem(r, 2, QTableWidgetItem(s.frequency))

    def _add_hospital(self):
        dlg = HospitalDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        m = dlg.get_model()

        h = table()
        _apply_model_to_hosp_tbl(h, m)
        self._hospitals().append(h)
        self._refresh_hospital_list()

        self.list_hosp.setCurrentRow(self.list_hosp.count() - 1)

    def _edit_hospital(self):
        row = self.list_hosp.currentRow()
        if row < 0 or row >= len(self._hospitals()):
            QMessageBox.information(self, "Info", "編集する病院を選択してください。")
            return

        h = self._hospitals()[row]
        initial = _hosp_tbl_to_model(h)

        dlg = HospitalDialog(self, initial)
        if dlg.exec() != QDialog.Accepted:
            return

        new_m = dlg.get_model()
        _apply_model_to_hosp_tbl(h, new_m)

        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(row)

    def _del_hospital(self):
        row = self.list_hosp.currentRow()
        if row < 0 or row >= len(self._hospitals()):
            QMessageBox.information(self, "Info", "削除する病院を選択してください。")
            return

        name = str(self._hospitals()[row].get("name", ""))
        ok = QMessageBox.question(self, "Confirm", f"削除しますか?\n{name}") == QMessageBox.Yes
        if not ok:
            return

        self._hospitals().pop(row)
        self._refresh_hospital_list()

    def _swap_hospitals(self, i: int, j: int):
        hosps = self._hospitals()
        if i < 0 or j < 0 or i >= len(hosps) or j >= len(hosps):
            return

        # tomlkit AoT is list-like: swap by pop/insert to be safe
        a = hosps[i]
        b = hosps[j]
        hosps[i] = b
        hosps[j] = a

        # Refresh UI and keep selection
        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(j)

    def _move_hospital_up(self):
        row = self.list_hosp.currentRow()
        if row <= 0:
            return
        self._swap_hospitals(row, row - 1)

    def _move_hospital_down(self):
        row = self.list_hosp.currentRow()
        hosps = self._hospitals()
        if row < 0 or row >= len(hosps) - 1:
            return
        self._swap_hospitals(row, row + 1)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open TOML", "", "TOML (*.toml);;All (*.*)")
        if not path:
            return

        try:
            text = Path(path).read_text(encoding="utf-8")
            self.doc = parse(text)
            self.current_path = Path(path)
            _ensure_hospitals(self.doc)
            self._refresh_hospital_list()
            self.statusBar().showMessage(f"Opened: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"読み込みに失敗しました:\n{e}")

    def _save_file(self):
        if self.current_path is None:
            self._save_file_as()
            return
        try:
            self.current_path.write_text(self.doc.as_string(), encoding="utf-8")
            self.statusBar().showMessage(f"Saved: {self.current_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"保存に失敗しました:\n{e}")

    def _save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save TOML As", "", "TOML (*.toml);;All (*.*)")
        if not path:
            return
        self.current_path = Path(path)
        self._save_file()


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1100, 650)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
