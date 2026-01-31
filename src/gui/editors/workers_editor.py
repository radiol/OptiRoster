"""Workers TOML editor — モデル⇔TOML変換ロジック + GUI ウィンドウ.

変換関数 (load/dump) は純 Python で動く。
GUI クラス (WorkersEditorWindow) は PySide6 が必要。
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import tomlkit
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# モデル型: list[dict] — 各要素は {"name", "is_diagnostic_specialist", "assignments"}
#   assignments は list[dict] — {"hospital", "weekdays", "shift_type"}
# ---------------------------------------------------------------------------
WorkerModel = list[dict[str, Any]]


def load_workers_toml(path: Path) -> WorkerModel:
    """TOML ファイルを読み込み、dict のリストとして返す."""
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
    """dict のリストを TOML ファイルに書き出す."""
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
# Assignments ⇔ TOML fragment 変換ヘルパー
# ---------------------------------------------------------------------------
def _format_assignments(assignments: list[dict[str, Any]]) -> str:
    """Assignments リストを TOML テキストに変換."""
    if not assignments:
        return ""
    doc = tomlkit.document()
    aot = tomlkit.aot()
    for a in assignments:
        t = tomlkit.table()
        t.add("hospital", a["hospital"])
        arr = tomlkit.array()
        for d in a["weekdays"]:
            arr.append(d)
        t.add("weekdays", arr)
        t.add("shift_type", a["shift_type"])
        aot.append(t)
    doc.add("assignments", aot)
    return tomlkit.dumps(doc)


def _parse_assignments(text: str) -> list[dict[str, Any]]:
    """TOML テキストを Assignments リストに変換."""
    if not text.strip():
        return []
    doc = tomlkit.parse(text)
    return [
        {
            "hospital": str(a["hospital"]),
            "weekdays": [str(d) for d in a.get("weekdays", [])],
            "shift_type": str(a["shift_type"]),
        }
        for a in doc.get("assignments", [])
    ]


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class WorkersEditorWindow(QMainWindow):
    """workers.toml 専用エディタウィンドウ(一覧+詳細)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workers Editor")
        self.resize(900, 600)
        self.current_path: Path | None = None
        self._model: WorkerModel = []
        self._current_index: int = -1

        # --- Left panel: worker list + Add/Delete ---
        self._worker_list = QListWidget()
        btn_add = QPushButton("Add")
        btn_delete = QPushButton("Delete")
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
        self._assignments_text = QPlainTextEdit()
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Name:"))
        right_layout.addWidget(self._name_edit)
        right_layout.addWidget(self._specialist_check)
        right_layout.addWidget(QLabel("Assignments (TOML):"))
        right_layout.addWidget(self._assignments_text)
        right_panel = QWidget()
        right_panel.setLayout(right_layout)

        # --- Splitter ---
        from PySide6.QtCore import Qt

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

    # --- public API ---
    def open_path(self, path: Path) -> None:
        """指定パスの workers.toml を読み込む."""
        try:
            self._model = load_workers_toml(path)
            self._current_index = -1
            self._refresh_list()
            self.current_path = path
            self.setWindowTitle(f"Workers Editor — {path.name}")
            if self._model:
                self._worker_list.setCurrentRow(0)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読み込みに失敗:\n{e}")

    def save_to(self, path: Path) -> None:
        """モデルを TOML ファイルに書き出す."""
        self._commit_current()
        dump_workers_toml(self._model, path)
        self.current_path = path
        self.setWindowTitle(f"Workers Editor — {path.name}")

    # --- private: model ⇔ form ---
    def _commit_current(self) -> None:
        """現在のフォーム状態をモデルに反映."""
        if self._current_index < 0 or self._current_index >= len(self._model):
            return
        w = self._model[self._current_index]
        w["name"] = self._name_edit.text()
        w["is_diagnostic_specialist"] = self._specialist_check.isChecked()
        with contextlib.suppress(Exception):  # パース失敗時は既存 assignments を維持
            w["assignments"] = _parse_assignments(self._assignments_text.toPlainText())
        item = self._worker_list.item(self._current_index)
        if item:
            item.setText(w["name"])

    def _load_worker_to_form(self, index: int) -> None:
        """指定インデックスの worker データをフォームに表示."""
        if index < 0 or index >= len(self._model):
            self._name_edit.clear()
            self._specialist_check.setChecked(False)
            self._assignments_text.clear()
            return
        w = self._model[index]
        self._name_edit.setText(w["name"])
        self._specialist_check.setChecked(w["is_diagnostic_specialist"])
        self._assignments_text.setPlainText(_format_assignments(w["assignments"]))

    def _refresh_list(self) -> None:
        """モデルからリストウィジェットを再構築."""
        self._worker_list.clear()
        for w in self._model:
            self._worker_list.addItem(w["name"])

    # --- private: slots ---
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
            self._assignments_text.clear()

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
