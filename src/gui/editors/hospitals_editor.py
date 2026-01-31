"""Hospitals TOML editor — モデル⇔TOML変換ロジック + GUI ウィンドウ.

変換関数 (load/dump) は純 Python で動く。
GUI クラス (HospitalsEditorWindow) は PySide6 が必要。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# モデル型: list[dict] — 各要素は {"name", "is_remote", "is_university", "shifts"}
#   shifts は list[dict] — {"shift_type", "weekdays", "frequency"}
# ---------------------------------------------------------------------------
HospitalModel = list[dict[str, Any]]


def load_hospitals_toml(path: Path) -> HospitalModel:
    """TOML ファイルを読み込み、dict のリストとして返す."""
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    doc = tomlkit.parse(text)
    result: HospitalModel = []
    for h in doc.get("hospitals", []):
        shifts = []
        for s in h.get("shifts", []):
            shifts.append(
                {
                    "shift_type": str(s["shift_type"]),
                    "weekdays": [str(w) for w in s.get("weekdays", [])],
                    "frequency": str(s.get("frequency", "毎週")),
                }
            )
        result.append(
            {
                "name": str(h["name"]),
                "is_remote": bool(h.get("is_remote", False)),
                "is_university": bool(h.get("is_university", False)),
                "shifts": shifts,
            }
        )
    return result


def dump_hospitals_toml(model: HospitalModel, path: Path) -> None:
    """dict のリストを TOML ファイルに書き出す."""
    doc = tomlkit.document()
    aot = tomlkit.aot()
    for h in model:
        tbl = tomlkit.table()
        tbl.add("name", h["name"])
        tbl.add("is_remote", h["is_remote"])
        tbl.add("is_university", h["is_university"])
        shifts_aot = tomlkit.aot()
        for s in h.get("shifts", []):
            st = tomlkit.table()
            st.add("shift_type", s["shift_type"])
            weekdays = tomlkit.array()
            for w in s["weekdays"]:
                weekdays.append(w)
            st.add("weekdays", weekdays)
            st.add("frequency", s["frequency"])
            shifts_aot.append(st)
        tbl.add("shifts", shifts_aot)
        aot.append(tbl)
    doc.add("hospitals", aot)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class HospitalsEditorWindow(QMainWindow):
    """hospitals.toml 専用エディタウィンドウ."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hospitals Editor")
        self.resize(800, 600)
        self.current_path: Path | None = None

        self._text_edit = QPlainTextEdit()
        toolbar = QHBoxLayout()
        btn_open = QPushButton("Open")
        btn_save = QPushButton("Save")
        btn_save_as = QPushButton("Save As")
        toolbar.addWidget(btn_open)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_save_as)
        toolbar.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(toolbar)
        layout.addWidget(self._text_edit)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        btn_open.clicked.connect(self._on_open)
        btn_save.clicked.connect(self._on_save)
        btn_save_as.clicked.connect(self._on_save_as)

    # --- public API ---
    def open_path(self, path: Path) -> None:
        """指定パスを読み込む."""
        self.load_toml(path)

    def load_toml(self, path: Path) -> None:
        """TOML ファイルを読み込んでエディタに表示."""
        try:
            text = path.read_text(encoding="utf-8-sig")
            self._text_edit.setPlainText(text)
            self.current_path = path
            self.setWindowTitle(f"Hospitals Editor — {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読み込みに失敗:\n{e}")

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open TOML", "", "TOML (*.toml)")
        if path:
            self.load_toml(Path(path))

    def _on_save(self) -> None:
        if self.current_path is None:
            self._on_save_as()
            return
        self._save_to(self.current_path)

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "TOML (*.toml)")
        if path:
            self.current_path = Path(path)
            self._save_to(self.current_path)

    def _save_to(self, path: Path) -> None:
        try:
            text = self._text_edit.toPlainText()
            tomlkit.parse(text)  # 構文検証
            path.write_text(text, encoding="utf-8")
            self.setWindowTitle(f"Hospitals Editor — {path.name}")
            QMessageBox.information(self, "保存完了", f"{path.name} を保存しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗:\n{e}")
