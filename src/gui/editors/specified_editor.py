"""Specified-dates TOML editor — モデル⇔TOML変換ロジック + GUI ウィンドウ.

変換関数 (load/dump) は純 Python で動く。
GUI クラス (SpecifiedDatesEditorWindow) は PySide6 が必要。
"""

from __future__ import annotations

from pathlib import Path

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
# モデル型: dict[str, list[int]] — 病院名→日付リスト
# ---------------------------------------------------------------------------
SpecifiedDatesModel = dict[str, list[int]]


def load_specified_dates(path: Path) -> SpecifiedDatesModel:
    """TOML ファイルを読み込み、{病院名: [日付…]} の dict を返す."""
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return {}
    doc = tomlkit.parse(text)
    result: SpecifiedDatesModel = {}
    for h in doc.get("hospitals", []):
        name = h.get("name")
        if name:
            result[str(name)] = [int(d) for d in h.get("dates", [])]
    return result


def dump_specified_dates(model: SpecifiedDatesModel, path: Path) -> None:
    """dict を TOML ファイルに書き出す."""
    doc = tomlkit.document()
    aot = tomlkit.aot()
    for name, dates in model.items():
        tbl = tomlkit.table()
        tbl.add("name", name)
        arr = tomlkit.array()
        for d in dates:
            arr.append(d)
        tbl.add("dates", arr)
        aot.append(tbl)
    doc.add("hospitals", aot)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class SpecifiedDatesEditorWindow(QMainWindow):
    """specified-dates.toml 専用エディタウィンドウ."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Specified Dates Editor")
        self.resize(700, 500)
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
        self.load_from_path(path)

    def load_from_path(self, path: Path) -> None:
        """TOML ファイルを読み込んでエディタに表示."""
        try:
            text = path.read_text(encoding="utf-8-sig")
            self._text_edit.setPlainText(text)
            self.current_path = path
            self.setWindowTitle(f"Specified Dates Editor — {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読み込みに失敗:\n{e}")

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open TOML", "", "TOML (*.toml)")
        if path:
            self.load_from_path(Path(path))

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
            self.setWindowTitle(f"Specified Dates Editor — {path.name}")
            QMessageBox.information(self, "保存完了", f"{path.name} を保存しました。")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗:\n{e}")
