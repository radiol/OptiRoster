"""IO roundtrip tests for CsvEditorWindow."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.editors.csv_editor import CsvEditorWindow

SAMPLE_CSV = """\
Name,病院1,病院2,病院3
診断01,,,
診断02,,1,
診断03,2,,0
"""


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def editor(qapp):
    w = CsvEditorWindow()
    yield w
    w.close()


class TestCsvEditorOpenPath:
    def test_open_sets_current_path(self, editor, tmp_path: Path):
        f = tmp_path / "test.csv"
        f.write_text(SAMPLE_CSV, encoding="utf-8")
        editor.open_path(f)
        assert editor.current_path == f

    def test_open_populates_table_rows(self, editor, tmp_path: Path):
        f = tmp_path / "test.csv"
        f.write_text(SAMPLE_CSV, encoding="utf-8")
        editor.open_path(f)
        assert editor._table.rowCount() == 3

    def test_open_populates_table_columns(self, editor, tmp_path: Path):
        f = tmp_path / "test.csv"
        f.write_text(SAMPLE_CSV, encoding="utf-8")
        editor.open_path(f)
        assert editor._table.columnCount() == 4  # Name + 3 hospitals

    def test_header_labels(self, editor, tmp_path: Path):
        f = tmp_path / "test.csv"
        f.write_text(SAMPLE_CSV, encoding="utf-8")
        editor.open_path(f)
        headers = [
            editor._table.horizontalHeaderItem(c).text() for c in range(editor._table.columnCount())
        ]
        assert headers == ["Name", "病院1", "病院2", "病院3"]


class TestCsvEditorRoundTrip:
    def test_save_and_reload_same_content(self, editor, tmp_path: Path):
        src = tmp_path / "in.csv"
        src.write_text(SAMPLE_CSV, encoding="utf-8")
        editor.open_path(src)

        out = tmp_path / "out.csv"
        editor.save_to(out)

        # 再読み込みして比較
        editor2 = CsvEditorWindow()
        editor2.open_path(out)

        assert editor2._table.rowCount() == editor._table.rowCount()
        assert editor2._table.columnCount() == editor._table.columnCount()

        for r in range(editor._table.rowCount()):
            for c in range(editor._table.columnCount()):
                orig = editor._table.item(r, c)
                reloaded = editor2._table.item(r, c)
                orig_text = orig.text() if orig else ""
                reloaded_text = reloaded.text() if reloaded else ""
                assert orig_text == reloaded_text, f"Mismatch at ({r},{c})"
        editor2.close()

    def test_save_produces_valid_csv(self, editor, tmp_path: Path):
        src = tmp_path / "in.csv"
        src.write_text(SAMPLE_CSV, encoding="utf-8")
        editor.open_path(src)

        out = tmp_path / "out.csv"
        editor.save_to(out)

        import csv

        with open(out, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        assert len(rows) == 4  # header + 3 data rows
        assert rows[0] == ["Name", "病院1", "病院2", "病院3"]


class TestCsvEditorEmptyFile:
    def test_open_empty_csv(self, editor, tmp_path: Path):
        f = tmp_path / "empty.csv"
        f.write_text("", encoding="utf-8")
        editor.open_path(f)
        assert editor._table.rowCount() == 0
