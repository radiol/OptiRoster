"""Hospitals TOML editor -- model/TOML conversion + GUI window.

Conversion functions are pure Python and GUI-independent.
GUI classes (ShiftDialog, HospitalDialog, HospitalsEditorWindow) require PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomlkit
from PySide6.QtWidgets import (
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHIFT_TYPES: list[str] = ["AM", "PM", "日勤", "当直"]
FREQUENCIES: list[str] = ["毎週", "隔週", "指定日"]
WEEKDAYS: list[str] = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]


# ---------------------------------------------------------------------------
# Model (dataclass)
# ---------------------------------------------------------------------------
@dataclass
class ShiftModel:
    shift_type: str
    weekdays: list[str] = field(default_factory=list)
    frequency: str = "毎週"


@dataclass
class HospitalModel:
    name: str
    is_remote: bool = False
    is_university: bool = False
    shifts: list[ShiftModel] = field(default_factory=list)


# ---------------------------------------------------------------------------
# tomlkit document helpers
# ---------------------------------------------------------------------------
def _ensure_hospitals(doc: tomlkit.TOMLDocument) -> tomlkit.items.AoT:
    """doc 内に hospitals AoT がなければ作り、返す."""
    if "hospitals" not in doc:
        doc["hospitals"] = aot()
    return doc["hospitals"]


def _ensure_shifts(hosp_tbl: tomlkit.items.Table) -> tomlkit.items.AoT:
    """hospital table 内に shifts AoT がなければ作り、返す."""
    if "shifts" not in hosp_tbl:
        hosp_tbl["shifts"] = aot()
    return hosp_tbl["shifts"]


def _hosp_tbl_to_model(h: tomlkit.items.Table) -> HospitalModel:
    """tomlkit table -> HospitalModel dataclass."""
    shifts: list[ShiftModel] = []
    if "shifts" in h and h["shifts"] is not None:
        shifts = [
            ShiftModel(
                shift_type=str(s.get("shift_type", "")),
                weekdays=[str(x) for x in (s.get("weekdays", []) or [])],
                frequency=str(s.get("frequency", "")),
            )
            for s in h["shifts"]
        ]
    return HospitalModel(
        name=str(h.get("name", "")),
        is_remote=bool(h.get("is_remote", False)),
        is_university=bool(h.get("is_university", False)),
        shifts=shifts,
    )


def _apply_model_to_hosp_tbl(
    hosp_tbl: tomlkit.items.Table,
    model: HospitalModel,
) -> None:
    """HospitalModel dataclass -> tomlkit table (in-place update)."""
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


# ---------------------------------------------------------------------------
# Public file-level IO (backward-compatible function names)
# ---------------------------------------------------------------------------
def load_hospitals_toml(path: Path) -> list[HospitalModel]:
    """TOML file -> list[HospitalModel]."""
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    doc = parse(text)
    return [_hosp_tbl_to_model(h) for h in doc.get("hospitals", [])]


def dump_hospitals_toml(model: list[HospitalModel], path: Path) -> None:
    """list[HospitalModel] -> TOML file."""
    doc = document()
    hospitals_aot = aot()
    for m in model:
        tbl = table()
        _apply_model_to_hosp_tbl(tbl, m)
        hospitals_aot.append(tbl)
    doc["hospitals"] = hospitals_aot
    path.write_text(doc.as_string(), encoding="utf-8")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------


class ShiftDialog(QDialog):
    """Shift (shift_type / weekdays / frequency) editing dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial: ShiftModel | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("シフト編集")

        self.combo_type = QComboBox()
        self.combo_type.addItems(SHIFT_TYPES)

        self.combo_freq = QComboBox()
        self.combo_freq.addItems(FREQUENCIES)

        self.week_checks: list[QCheckBox] = []
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

    def _validate_then_accept(self) -> None:
        weekdays = [cb.text() for cb in self.week_checks if cb.isChecked()]
        if not weekdays:
            QMessageBox.warning(self, "Error", "Weekdays は1つ以上選択してください。")
            return
        self.accept()


class HospitalDialog(QDialog):
    """Hospital (name / flags / shifts) editing dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial: HospitalModel | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("病院編集")

        self.edit_name = QLineEdit()
        self.chk_remote = QCheckBox("遠隔地か?")
        self.chk_univ = QCheckBox("大学病院か?")

        self.shift_table = QTableWidget(0, 3)
        self.shift_table.setHorizontalHeaderLabels(["shift_type", "weekdays", "frequency"])
        self.shift_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.shift_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
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

    # -- shift table helpers --
    def _append_shift_row(self, s: ShiftModel) -> None:
        r = self.shift_table.rowCount()
        self.shift_table.insertRow(r)
        self.shift_table.setItem(r, 0, QTableWidgetItem(s.shift_type))
        self.shift_table.setItem(r, 1, QTableWidgetItem(",".join(s.weekdays)))
        self.shift_table.setItem(r, 2, QTableWidgetItem(s.frequency))

    def _row_to_shift(self, row: int) -> ShiftModel:
        stype = self.shift_table.item(row, 0)
        wds = self.shift_table.item(row, 1)
        freq = self.shift_table.item(row, 2)
        weekdays = [x for x in (wds.text() if wds else "").split(",") if x]
        return ShiftModel(
            shift_type=stype.text() if stype else "",
            weekdays=weekdays,
            frequency=freq.text() if freq else "",
        )

    def _selected_row(self) -> int | None:
        items = self.shift_table.selectedItems()
        if not items:
            return None
        return items[0].row()

    def _add_shift(self) -> None:
        dlg = ShiftDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._append_shift_row(dlg.get_model())

    def _edit_shift(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "編集するシフトを選択してください。")
            return
        current = self._row_to_shift(row)
        dlg = ShiftDialog(self, current)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            m = dlg.get_model()
            self.shift_table.item(row, 0).setText(m.shift_type)
            self.shift_table.item(row, 1).setText(",".join(m.weekdays))
            self.shift_table.item(row, 2).setText(m.frequency)

    def _del_shift(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "Info", "削除するシフトを選択してください。")
            return
        self.shift_table.removeRow(row)

    def _validate_then_accept(self) -> None:
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "病院名 (name) は必須です。")
            return
        for r in range(self.shift_table.rowCount()):
            stype = (self.shift_table.item(r, 0) or QTableWidgetItem("")).text().strip()
            freq = (self.shift_table.item(r, 2) or QTableWidgetItem("")).text().strip()
            if stype not in SHIFT_TYPES:
                QMessageBox.warning(self, "Error", f"shift_type が不正です: row={r + 1}")
                return
            if freq not in FREQUENCIES:
                QMessageBox.warning(self, "Error", f"frequency が不正です: row={r + 1}")
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


# ---------------------------------------------------------------------------
# Main editor window
# ---------------------------------------------------------------------------
class HospitalsEditorWindow(QMainWindow):
    """hospitals.toml GUI editor -- list + detail + dialogs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hospitals Editor")
        self.resize(1100, 650)
        self.current_path: Path | None = None
        self.doc: tomlkit.TOMLDocument = document()

        # -- left: hospital list --
        self.list_hosp = QListWidget()
        self.list_hosp.currentRowChanged.connect(self._on_select_hospital)
        self.list_hosp.itemDoubleClicked.connect(lambda _: self._edit_hospital())

        btn_add = QPushButton("病院 新規追加")
        btn_edit = QPushButton("病院 編集")
        btn_del = QPushButton("病院 削除")
        btn_add.clicked.connect(self._add_hospital)
        btn_edit.clicked.connect(self._edit_hospital)
        btn_del.clicked.connect(self._del_hospital)

        btn_up = QPushButton("↑ 上へ")
        btn_down = QPushButton("↓ 下へ")
        btn_up.clicked.connect(self._move_hospital_up)
        btn_down.clicked.connect(self._move_hospital_down)

        crud_btns = QHBoxLayout()
        crud_btns.addWidget(btn_add)
        crud_btns.addWidget(btn_edit)
        crud_btns.addWidget(btn_del)

        move_btns = QHBoxLayout()
        move_btns.addWidget(btn_up)
        move_btns.addWidget(btn_down)
        move_btns.addStretch(1)

        # -- right: detail view --
        self._lbl_name = QLabel("-")
        self._lbl_flags = QLabel("-")
        self._shift_table = QTableWidget(0, 3)
        self._shift_table.setHorizontalHeaderLabels(["shift_type", "weekdays", "frequency"])
        self._shift_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._shift_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._shift_table.horizontalHeader().setStretchLastSection(True)

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
        left.addWidget(QLabel("Hospitals"))
        left.addWidget(self.list_hosp)
        left.addLayout(move_btns)
        left.addLayout(crud_btns)

        right = QVBoxLayout()
        right.addWidget(QLabel("Selected hospital"))
        right.addWidget(self._lbl_name)
        right.addWidget(self._lbl_flags)
        right.addSpacing(8)
        right.addWidget(QLabel("Shifts"))
        right.addWidget(self._shift_table)

        root = QHBoxLayout()
        root.addLayout(left, 2)
        root.addLayout(right, 3)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._build_menu()
        self._refresh_hospital_list()

    # -- public API --
    def open_path(self, path: Path) -> None:
        """Load a TOML file and refresh the UI."""
        try:
            text = path.read_text(encoding="utf-8-sig")
            self.doc = parse(text) if text.strip() else document()
            _ensure_hospitals(self.doc)
            self.current_path = path
            self.setWindowTitle(f"Hospitals Editor \u2014 {path.name}")
            self._refresh_hospital_list()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読み込みに失敗:\n{e}")

    def save_to(self, path: Path) -> None:
        """Write the current doc to *path*."""
        path.write_text(self.doc.as_string(), encoding="utf-8")
        self.current_path = path
        self.setWindowTitle(f"Hospitals Editor \u2014 {path.name}")

    # -- menu --
    def _build_menu(self) -> None:
        m_file = self.menuBar().addMenu("File")
        act_open = m_file.addAction("Open...")
        act_save = m_file.addAction("Save")
        act_save_as = m_file.addAction("Save As...")
        act_open.triggered.connect(self._on_open)
        act_save.triggered.connect(self._on_save)
        act_save_as.triggered.connect(self._on_save_as)

    # -- hospitals AoT accessor --
    def _hospitals(self) -> tomlkit.items.AoT:
        return _ensure_hospitals(self.doc)

    # -- list refresh --
    def _refresh_hospital_list(self) -> None:
        self.list_hosp.clear()
        for h in self._hospitals():
            self.list_hosp.addItem(QListWidgetItem(str(h.get("name", ""))))
        if self.list_hosp.count() > 0 and self.list_hosp.currentRow() < 0:
            self.list_hosp.setCurrentRow(0)
        else:
            self._on_select_hospital(self.list_hosp.currentRow())

    def _on_select_hospital(self, row: int) -> None:
        self._shift_table.setRowCount(0)
        hosps = self._hospitals()
        if row < 0 or row >= len(hosps):
            self._lbl_name.setText("-")
            self._lbl_flags.setText("-")
            return
        m = _hosp_tbl_to_model(hosps[row])
        self._lbl_name.setText(f"name: {m.name}")
        self._lbl_flags.setText(f"is_remote: {m.is_remote}   is_university: {m.is_university}")
        for s in m.shifts:
            r = self._shift_table.rowCount()
            self._shift_table.insertRow(r)
            self._shift_table.setItem(r, 0, QTableWidgetItem(s.shift_type))
            self._shift_table.setItem(r, 1, QTableWidgetItem(",".join(s.weekdays)))
            self._shift_table.setItem(r, 2, QTableWidgetItem(s.frequency))

    # -- CRUD --
    def _add_hospital(self) -> None:
        dlg = HospitalDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        h = table()
        _apply_model_to_hosp_tbl(h, dlg.get_model())
        self._hospitals().append(h)
        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(self.list_hosp.count() - 1)

    def _edit_hospital(self) -> None:
        row = self.list_hosp.currentRow()
        hosps = self._hospitals()
        if row < 0 or row >= len(hosps):
            QMessageBox.information(self, "Info", "編集する病院を選択してください。")
            return
        initial = _hosp_tbl_to_model(hosps[row])
        dlg = HospitalDialog(self, initial)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        _apply_model_to_hosp_tbl(hosps[row], dlg.get_model())
        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(row)

    def _del_hospital(self) -> None:
        row = self.list_hosp.currentRow()
        hosps = self._hospitals()
        if row < 0 or row >= len(hosps):
            QMessageBox.information(self, "Info", "削除する病院を選択してください。")
            return
        name = str(hosps[row].get("name", ""))
        if (
            QMessageBox.question(self, "Confirm", f"削除しますか?\n{name}")
            != QMessageBox.StandardButton.Yes
        ):
            return
        hosps.pop(row)
        self._refresh_hospital_list()

    # -- move --
    def _swap_hospitals(self, i: int, j: int) -> None:
        hosps = self._hospitals()
        if i < 0 or j < 0 or i >= len(hosps) or j >= len(hosps):
            return
        hosps[i], hosps[j] = hosps[j], hosps[i]
        self._refresh_hospital_list()
        self.list_hosp.setCurrentRow(j)

    def _move_hospital_up(self) -> None:
        row = self.list_hosp.currentRow()
        if row > 0:
            self._swap_hospitals(row, row - 1)

    def _move_hospital_down(self) -> None:
        row = self.list_hosp.currentRow()
        if 0 <= row < len(self._hospitals()) - 1:
            self._swap_hospitals(row, row + 1)

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
