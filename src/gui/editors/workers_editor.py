"""Workers TOML editor -- model/TOML conversion logic + GUI window.

Conversion functions (load/dump) are pure Python and GUI-independent.
GUI classes (AssignmentDialog, WorkersEditorWindow) require PySide6.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
from PySide6.QtCore import Qt
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
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.gui.editors.hospitals_editor import SHIFT_TYPES, WEEKDAYS
from src.io.hospitals_loader import load_hospitals

# ---------------------------------------------------------------------------
# Model type: list[dict] -- each element has {"name", "is_diagnostic_specialist", "assignments"}
#   assignments is list[dict] -- {"hospital", "weekdays", "shift_type"}
# ---------------------------------------------------------------------------
WorkerModel = list[dict[str, Any]]


def load_workers_toml(path: Path) -> WorkerModel:
    """Read a TOML file and return it as a list of dicts."""
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    doc = tomlkit.parse(text)
    result: WorkerModel = []
    for w in doc.get("workers", []):
        assignments: list[dict[str, Any]] = [
            {
                "hospital": str(a["hospital"]),
                "weekdays": [str(d) for d in a.get("weekdays", [])],
                "shift_type": str(a["shift_type"]),
            }
            for a in w.get("assignments", [])
        ]
        result.append(
            {
                "name": str(w["name"]),
                "is_diagnostic_specialist": bool(w.get("is_diagnostic_specialist", False)),
                "assignments": assignments,
            }
        )
    return result


def dump_workers_toml(model: WorkerModel, path: Path) -> None:
    """Write a list of dicts to a TOML file."""
    doc = tomlkit.document()
    aot = tomlkit.aot()
    for w in model:
        tbl = tomlkit.table()
        tbl.add("name", w["name"])
        tbl.add("is_diagnostic_specialist", w["is_diagnostic_specialist"])
        assignments = w.get("assignments", [])
        if assignments:
            assignments_aot = tomlkit.aot()
            for a in assignments:
                at = tomlkit.table()
                at.add("hospital", a["hospital"])
                weekdays = tomlkit.array()
                for d in a["weekdays"]:
                    weekdays.append(d)
                at.add("weekdays", weekdays)
                at.add("shift_type", a["shift_type"])
                assignments_aot.append(at)
            tbl.add("assignments", assignments_aot)
        aot.append(tbl)
    doc.add("workers", aot)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# Pure logic helpers for assignment GUI
# ---------------------------------------------------------------------------
def load_hospital_choices(path: Path) -> list[str]:
    """Read hospital names from hospitals.toml. Returns [] on any failure."""
    if not path.exists():
        return []
    try:
        models = load_hospitals(str(path))
    except Exception:
        return []
    return [m.name for m in models]


def build_combo_choices(known: list[str], current: str) -> list[str]:
    """Build combo box items: known hospitals + unknown current (if any)."""
    if not current:
        return list(known)
    if current in known:
        return list(known)
    return [current, *known]


def format_assignment_summary(a: dict[str, Any]) -> str:
    """Format an assignment dict as a one-line summary string."""
    weekdays_str = ",".join(a.get("weekdays", []))
    return f"{a.get('hospital', '')} / {a.get('shift_type', '')} / {weekdays_str}"


# ---------------------------------------------------------------------------
# AssignmentDialog
# ---------------------------------------------------------------------------
class AssignmentDialog(QDialog):
    """Assignment (hospital / weekdays / shift_type) editing dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial: dict[str, Any] | None = None,
        hospital_choices: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assignment")

        # Hospital combo (editable for unknown names)
        self.combo_hospital = QComboBox()
        self.combo_hospital.setEditable(True)
        if hospital_choices:
            self.combo_hospital.addItems(hospital_choices)
        if initial and initial.get("hospital"):
            self.combo_hospital.setCurrentText(initial["hospital"])
        else:
            self.combo_hospital.setCurrentText("")

        # Shift type combo
        self.combo_shift_type = QComboBox()
        self.combo_shift_type.addItems(SHIFT_TYPES)

        # Weekday checkboxes
        self.week_checks: list[QCheckBox] = []
        week_box = QGroupBox("Weekdays")
        grid = QGridLayout()
        for i, wd in enumerate(WEEKDAYS):
            cb = QCheckBox(wd)
            self.week_checks.append(cb)
            grid.addWidget(cb, i // 4, i % 4)
        week_box.setLayout(grid)

        form = QFormLayout()
        form.addRow("hospital", self.combo_hospital)
        form.addRow("shift_type", self.combo_shift_type)

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

        # Apply initial values
        if initial:
            if initial.get("shift_type") in SHIFT_TYPES:
                self.combo_shift_type.setCurrentText(initial["shift_type"])
            wset = set(initial.get("weekdays", []))
            for cb in self.week_checks:
                cb.setChecked(cb.text() in wset)

    def get_assignment(self) -> dict[str, Any]:
        """Return the current assignment as a dict."""
        weekdays = [cb.text() for cb in self.week_checks if cb.isChecked()]
        return {
            "hospital": self.combo_hospital.currentText(),
            "weekdays": weekdays,
            "shift_type": self.combo_shift_type.currentText(),
        }

    def _validate_then_accept(self) -> None:
        hospital = self.combo_hospital.currentText().strip()
        if not hospital:
            QMessageBox.warning(self, "Error", "hospital は必須です。")
            return
        weekdays = [cb.text() for cb in self.week_checks if cb.isChecked()]
        if not weekdays:
            QMessageBox.warning(self, "Error", "Weekdays は1つ以上選択してください。")
            return
        self.accept()


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class WorkersEditorWindow(QMainWindow):
    """workers.toml editor window (worker list + detail form with assignment list)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workers Editor")
        self.resize(900, 600)
        self.current_path: Path | None = None
        self._model: WorkerModel = []
        self._current_index: int = -1
        self._hospitals_path: Path | None = None

        # --- Left panel: worker list + Add/Delete ---
        self._worker_list = QListWidget()
        btn_add = QPushButton("メンバー追加")
        btn_delete = QPushButton("メンバー削除")
        left_btns = QHBoxLayout()
        left_btns.addWidget(btn_add)
        left_btns.addWidget(btn_delete)
        left_layout = QVBoxLayout()
        left_layout.addWidget(self._worker_list)
        left_layout.addLayout(left_btns)
        left_panel = QWidget()
        left_panel.setLayout(left_layout)

        # --- Right panel: detail form ---
        self._name_edit = QLineEdit()
        self._specialist_check = QCheckBox("診断専門医")

        # Assignments list + CRUD buttons
        self._assignments_list = QListWidget()
        btn_assign_add = QPushButton("追加")
        btn_assign_edit = QPushButton("編集")
        btn_assign_del = QPushButton("削除")
        assign_btns = QHBoxLayout()
        assign_btns.addWidget(btn_assign_add)
        assign_btns.addWidget(btn_assign_edit)
        assign_btns.addWidget(btn_assign_del)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Name:"))
        right_layout.addWidget(self._name_edit)
        right_layout.addWidget(self._specialist_check)
        right_layout.addWidget(QLabel("Assignments:"))
        right_layout.addWidget(self._assignments_list)
        right_layout.addLayout(assign_btns)
        right_panel = QWidget()
        right_panel.setLayout(right_layout)

        # --- Splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        # --- Toolbar ---
        toolbar = QHBoxLayout()
        btn_open = QPushButton("Open")
        btn_save = QPushButton("Save")
        btn_save_as = QPushButton("Save As")
        toolbar.addWidget(btn_open)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_save_as)
        toolbar.addStretch()

        # --- Main layout ---
        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(splitter)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        # --- Connections ---
        btn_open.clicked.connect(self._on_open)
        btn_save.clicked.connect(self._on_save)
        btn_save_as.clicked.connect(self._on_save_as)
        btn_add.clicked.connect(self._on_add)
        btn_delete.clicked.connect(self._on_delete)
        self._worker_list.currentRowChanged.connect(self._on_selection_changed)
        btn_assign_add.clicked.connect(self._on_add_assignment)
        btn_assign_edit.clicked.connect(self._on_edit_assignment)
        btn_assign_del.clicked.connect(self._on_delete_assignment)
        self._assignments_list.itemDoubleClicked.connect(lambda _: self._on_edit_assignment())

    # --- public API ---
    def open_path(self, path: Path) -> None:
        """Load a workers.toml file."""
        try:
            self._model = load_workers_toml(path)
            self._current_index = -1
            self._refresh_list()
            self.current_path = path
            self.setWindowTitle(f"Workers Editor \u2014 {path.name}")
            if self._model:
                self._worker_list.setCurrentRow(0)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load:\n{e}")

    def save_to(self, path: Path) -> None:
        """Write model to a TOML file."""
        self._commit_current()
        dump_workers_toml(self._model, path)
        self.current_path = path
        self.setWindowTitle(f"Workers Editor \u2014 {path.name}")

    def set_hospitals_path(self, path: Path) -> None:
        """Set the path to hospitals.toml for hospital name choices."""
        self._hospitals_path = path

    # --- private: hospital choices ---
    def _get_hospital_choices(self, current: str = "") -> list[str]:
        """Build hospital combo choices from hospitals.toml + current value."""
        known: list[str] = []
        if self._hospitals_path is not None:
            known = load_hospital_choices(self._hospitals_path)
        return build_combo_choices(known, current)

    # --- private: model <-> form ---
    def _commit_current(self) -> None:
        """Commit form state to the model."""
        if self._current_index < 0 or self._current_index >= len(self._model):
            return
        w = self._model[self._current_index]
        w["name"] = self._name_edit.text()
        w["is_diagnostic_specialist"] = self._specialist_check.isChecked()
        # Assignments are updated directly via dialog, no text parsing needed
        item = self._worker_list.item(self._current_index)
        if item:
            item.setText(w["name"])

    def _load_worker_to_form(self, index: int) -> None:
        """Display worker data in the detail form."""
        if index < 0 or index >= len(self._model):
            self._name_edit.clear()
            self._specialist_check.setChecked(False)
            self._assignments_list.clear()
            return
        w = self._model[index]
        self._name_edit.setText(w["name"])
        self._specialist_check.setChecked(w["is_diagnostic_specialist"])
        self._refresh_assignments_list(w.get("assignments", []))

    def _refresh_assignments_list(self, assignments: list[dict[str, Any]]) -> None:
        """Rebuild the assignments list widget from data."""
        self._assignments_list.clear()
        for a in assignments:
            self._assignments_list.addItem(format_assignment_summary(a))

    def _refresh_list(self) -> None:
        """Rebuild the worker list widget from the model."""
        self._worker_list.clear()
        for w in self._model:
            self._worker_list.addItem(w["name"])

    # --- private: worker CRUD slots ---
    def _on_selection_changed(self, row: int) -> None:
        self._commit_current()
        self._current_index = row
        self._load_worker_to_form(row)

    def _on_add(self) -> None:
        self._commit_current()
        new_worker: dict[str, Any] = {
            "name": "New Worker",
            "is_diagnostic_specialist": False,
            "assignments": [],
        }
        self._model.append(new_worker)
        self._worker_list.addItem(new_worker["name"])
        self._worker_list.setCurrentRow(len(self._model) - 1)

    def _on_delete(self) -> None:
        row = self._worker_list.currentRow()
        if row < 0:
            return
        self._current_index = -1
        self._model.pop(row)
        self._worker_list.takeItem(row)
        if self._model:
            new_row = min(row, len(self._model) - 1)
            self._worker_list.setCurrentRow(new_row)
        else:
            self._name_edit.clear()
            self._specialist_check.setChecked(False)
            self._assignments_list.clear()

    # --- private: assignment CRUD slots ---
    def _on_add_assignment(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._model):
            return
        choices = self._get_hospital_choices()
        dlg = AssignmentDialog(self, hospital_choices=choices)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        a = dlg.get_assignment()
        w = self._model[self._current_index]
        w["assignments"].append(a)
        self._assignments_list.addItem(format_assignment_summary(a))

    def _on_edit_assignment(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._model):
            return
        arow = self._assignments_list.currentRow()
        w = self._model[self._current_index]
        assignments = w.get("assignments", [])
        if arow < 0 or arow >= len(assignments):
            QMessageBox.information(self, "Info", "編集する assignment を選択してください。")
            return
        current_a = assignments[arow]
        choices = self._get_hospital_choices(current_a.get("hospital", ""))
        dlg = AssignmentDialog(self, initial=current_a, hospital_choices=choices)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_a = dlg.get_assignment()
        assignments[arow] = new_a
        item = self._assignments_list.item(arow)
        if item:
            item.setText(format_assignment_summary(new_a))

    def _on_delete_assignment(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._model):
            return
        arow = self._assignments_list.currentRow()
        w = self._model[self._current_index]
        assignments = w.get("assignments", [])
        if arow < 0 or arow >= len(assignments):
            QMessageBox.information(self, "Info", "削除する assignment を選択してください。")
            return
        assignments.pop(arow)
        self._assignments_list.takeItem(arow)

    # --- private: file operation slots ---
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
