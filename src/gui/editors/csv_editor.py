"""CSV editor -- QTableWidget-based editing window for max-assignments.csv.

Uses src/io/max_assignments_loader and max_assignments_writer for IO.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.io.max_assignments_loader import load_max_assignments_csv
from src.io.max_assignments_writer import dump_max_assignments_csv


class CsvEditorWindow(QMainWindow):
    """max-assignments.csv を QTableWidget で編集するウィンドウ."""

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

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        toolbar.addWidget(sep1)

        btn_add_row = QPushButton("行追加")
        btn_del_row = QPushButton("行削除")
        toolbar.addWidget(btn_add_row)
        toolbar.addWidget(btn_del_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        toolbar.addWidget(sep2)

        btn_add_col = QPushButton("列追加")
        btn_del_col = QPushButton("列削除")
        toolbar.addWidget(btn_add_col)
        toolbar.addWidget(btn_del_col)

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
        btn_add_row.clicked.connect(self._on_add_row)
        btn_del_row.clicked.connect(self._on_delete_row)
        btn_add_col.clicked.connect(self._on_add_column)
        btn_del_col.clicked.connect(self._on_delete_column)

        self._install_key_filter()

    # --- public API ---
    def open_path(self, path: Path) -> None:
        """CSV ファイルを読み込んでテーブルに表示する."""
        try:
            if not path.read_text(encoding="utf-8-sig").strip():
                self._table.clear()
                self._table.setRowCount(0)
                self._table.setColumnCount(0)
                self.current_path = path
                self.setWindowTitle(f"CSV Editor \u2014 {path.name}")
                return
            data = load_max_assignments_csv(str(path))
            self._populate_table(data)
            self.current_path = path
            self.setWindowTitle(f"CSV Editor \u2014 {path.name}")
        except Exception as e:
            QMessageBox.critical(
                self, "\u30a8\u30e9\u30fc", f"\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557:\n{e}"
            )

    def save_to(self, path: Path) -> None:
        """テーブルの内容を CSV に書き出す."""
        data = self._read_table_model()
        dump_max_assignments_csv(data, str(path))
        self.current_path = path
        self.setWindowTitle(f"CSV Editor \u2014 {path.name}")

    # --- private: model <-> table ---
    def _populate_table(self, data: dict[tuple[str, str], int | None]) -> None:
        """Populate the QTableWidget from a max-assignments dict."""
        workers: list[str] = []
        hospitals: list[str] = []
        workers_seen: set[str] = set()
        hospitals_seen: set[str] = set()
        for worker, hospital in data:
            if worker not in workers_seen:
                workers.append(worker)
                workers_seen.add(worker)
            if hospital not in hospitals_seen:
                hospitals.append(hospital)
                hospitals_seen.add(hospital)

        self._table.clear()
        self._table.setColumnCount(1 + len(hospitals))
        self._table.setRowCount(len(workers))
        self._table.setHorizontalHeaderLabels(["Name", *hospitals])

        for r, worker in enumerate(workers):
            self._table.setItem(r, 0, QTableWidgetItem(worker))
            for c, hospital in enumerate(hospitals):
                cap = data.get((worker, hospital))
                text = "" if cap is None else str(cap)
                self._table.setItem(r, c + 1, QTableWidgetItem(text))

        self._table.resizeColumnsToContents()

    def _read_table_model(self) -> dict[tuple[str, str], int | None]:
        """Read the QTableWidget into a max-assignments dict."""
        data: dict[tuple[str, str], int | None] = {}
        cols = self._table.columnCount()
        rows = self._table.rowCount()

        hospitals: list[str] = []
        for c in range(1, cols):
            h = self._table.horizontalHeaderItem(c)
            hospitals.append(h.text() if h else f"col{c}")

        for r in range(rows):
            name_item = self._table.item(r, 0)
            name = (name_item.text() if name_item else "").strip()
            if not name:
                continue
            for c, hospital in enumerate(hospitals):
                item = self._table.item(r, c + 1)
                raw = (item.text() if item else "").strip()
                if raw == "":
                    cap: int | None = None
                else:
                    cap = int(raw)
                data[(name, hospital)] = cap

        return data

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
        QMessageBox.information(
            self,
            "\u4fdd\u5b58\u5b8c\u4e86",
            f"{self.current_path.name} \u3092\u4fdd\u5b58\u3057\u307e\u3057\u305f\u3002",
        )

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save As", "", "CSV (*.csv)")
        if path:
            self.save_to(Path(path))
            QMessageBox.information(
                self,
                "\u4fdd\u5b58\u5b8c\u4e86",
                f"{Path(path).name} \u3092\u4fdd\u5b58\u3057\u307e\u3057\u305f\u3002",
            )

    def _on_add_row(self) -> None:
        """選択行の下に空行を挿入する. 未選択なら末尾に追加."""
        row = self._table.currentRow()
        pos = row + 1 if row >= 0 else self._table.rowCount()
        self._table.insertRow(pos)
        for c in range(self._table.columnCount()):
            self._table.setItem(pos, c, QTableWidgetItem(""))
        self._table.setCurrentCell(pos, 0)

    def _on_delete_row(self) -> None:
        """選択行を削除する."""
        row = self._table.currentRow()
        if row < 0:
            return
        self._table.removeRow(row)

    def _on_add_column(self) -> None:
        """入力ダイアログで病院名を受け取り, 末尾列に追加する."""
        name, ok = QInputDialog.getText(self, "列追加", "列名:")
        if not ok or not name.strip():
            return
        col = self._table.columnCount()
        self._table.insertColumn(col)
        self._table.setHorizontalHeaderItem(col, QTableWidgetItem(name.strip()))
        for r in range(self._table.rowCount()):
            self._table.setItem(r, col, QTableWidgetItem(""))

    def _on_delete_column(self) -> None:
        """選択セルの列を削除する. Name列(col 0)は削除禁止."""
        col = self._table.currentColumn()
        if col <= 0:
            return
        self._table.removeColumn(col)

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
