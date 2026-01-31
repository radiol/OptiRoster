"""CSV editor — QTableWidget ベースの編集ウィンドウ.

max-assignments.csv 等を表形式で編集し、Open / Save / Save As を提供する。
.bak は作らない(Save As で代替)。
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CsvEditorWindow(QMainWindow):
    """CSV ファイルを QTableWidget で編集するウィンドウ."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CSV Editor")
        self.resize(900, 600)
        self.current_path: Path | None = None

        self._table = QTableWidget()

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
        layout.addWidget(self._table)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        btn_open.clicked.connect(self._on_open)
        btn_save.clicked.connect(self._on_save)
        btn_save_as.clicked.connect(self._on_save_as)

        self._install_key_filter()

    # --- public API ---
    def open_path(self, path: Path) -> None:
        """CSV ファイルを読み込んでテーブルに表示する."""
        try:
            text = path.read_text(encoding="utf-8-sig")
            if not text.strip():
                self._table.clear()
                self._table.setRowCount(0)
                self._table.setColumnCount(0)
                self.current_path = path
                self.setWindowTitle(f"CSV Editor — {path.name}")
                return
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                return
            headers = rows[0]
            data = rows[1:]
            self._table.clear()
            self._table.setColumnCount(len(headers))
            self._table.setRowCount(len(data))
            self._table.setHorizontalHeaderLabels(headers)
            for r, row in enumerate(data):
                for c, val in enumerate(row):
                    self._table.setItem(r, c, QTableWidgetItem(val))
            self._table.resizeColumnsToContents()
            self.current_path = path
            self.setWindowTitle(f"CSV Editor — {path.name}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読み込みに失敗:\n{e}")

    def save_to(self, path: Path) -> None:
        """テーブルの内容を CSV に書き出す."""
        rows_count = self._table.rowCount()
        cols_count = self._table.columnCount()
        headers = []
        for c in range(cols_count):
            h = self._table.horizontalHeaderItem(c)
            headers.append(h.text() if h else f"col{c}")
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(headers)
        for r in range(rows_count):
            row = []
            for c in range(cols_count):
                item = self._table.item(r, c)
                row.append(item.text() if item else "")
            writer.writerow(row)
        path.write_text(buf.getvalue(), encoding="utf-8")
        self.current_path = path
        self.setWindowTitle(f"CSV Editor — {path.name}")

    # --- private ---
    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV (*.csv)")
        if path:
            self.open_path(Path(path))

    def _on_save(self) -> None:
        if self.current_path is None:
            self._on_save_as()
            return
        self.save_to(self.current_path)
        QMessageBox.information(self, "保存完了", f"{self.current_path.name} を保存しました。")

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "CSV (*.csv)")
        if path:
            self.save_to(Path(path))
            QMessageBox.information(self, "保存完了", f"{Path(path).name} を保存しました。")

    def _install_key_filter(self) -> None:
        """Delete / Backspace でセルクリアを有効にする."""
        from PySide6.QtCore import QEvent, QObject
        from PySide6.QtGui import QKeyEvent

        table = self._table

        class _Filter(QObject):
            def eventFilter(self, obj: QObject, event: QEvent) -> bool:
                if event.type() == QEvent.Type.KeyPress and obj is table:
                    key_event: QKeyEvent = event  # type: ignore[assignment]
                    if key_event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                        item = table.currentItem()
                        if item is not None:
                            item.setText("")
                            return True
                return False

        self._filter = _Filter(self)
        table.installEventFilter(self._filter)
