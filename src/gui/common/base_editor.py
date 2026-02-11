"""Editor windows base class -- common file operation slots."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QWidget,
)


class BaseEditorWindow(QMainWindow):
    """エディタウィンドウ共通基底. _on_open / _on_save / _on_save_as を提供する.

    サブクラスは以下を定義すること:
    - _file_filter: str  (例: "CSV (*.csv)")
    - open_path(path) -> None
    - save_to(path) -> None
    """

    _file_filter: str = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_path: Path | None = None

    def open_path(self, path: Path) -> None:
        raise NotImplementedError

    def save_to(self, path: Path) -> None:
        raise NotImplementedError

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open", "", self._file_filter)
        if path:
            self.open_path(Path(path))

    def _on_save(self) -> None:
        if self.current_path is None:
            self._on_save_as()
            return
        self.save_to(self.current_path)
        QMessageBox.information(self, "保存完了", f"{self.current_path.name} を保存しました。")

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", self._file_filter)
        if path:
            self.save_to(Path(path))
            QMessageBox.information(self, "保存完了", f"{Path(path).name} を保存しました。")
