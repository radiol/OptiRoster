"""IO roundtrip tests for WorkersEditorWindow."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.editors.workers_editor import WorkersEditorWindow
from src.io.workers_loader import load_workers

SAMPLE_WORKERS_TOML = """\
[[workers]]
name = "診断01"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院1"
weekdays = ["月曜", "火曜"]
shift_type = "日勤"

[[workers]]
name = "診断02"
is_diagnostic_specialist = false
"""


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def editor(qapp):
    w = WorkersEditorWindow()
    yield w
    w.close()


class TestWorkersEditorOpenSave:
    def test_open_sets_current_path(self, editor, tmp_path: Path):
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(f)
        assert editor.current_path == f

    def test_open_populates_worker_list(self, editor, tmp_path: Path):
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(f)
        assert editor._worker_list.count() == 2

    def test_save_and_reload_roundtrip(self, editor, tmp_path: Path):
        src = tmp_path / "in.toml"
        src.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(src)
        out = tmp_path / "out.toml"
        editor.save_to(out)
        workers = load_workers(str(out))
        assert len(workers) == 2
        assert workers[0].name == "診断01"
        assert workers[1].name == "診断02"

    def test_load_workers_compatibility(self, editor, tmp_path: Path):
        """Saved file must be loadable by the existing load_workers()."""
        src = tmp_path / "in.toml"
        src.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(src)
        out = tmp_path / "out.toml"
        editor.save_to(out)
        workers = load_workers(str(out))
        assert len(workers) == 2
        assert workers[0].name == "診断01"
        assert workers[0].is_diagnostic_specialist is True
        assert len(workers[0].assignments) == 1
        assert workers[1].name == "診断02"


class TestWorkersEditorEmptyFile:
    def test_open_empty_toml(self, editor, tmp_path: Path):
        f = tmp_path / "empty.toml"
        f.write_text("", encoding="utf-8")
        editor.open_path(f)
        assert editor.current_path == f
        assert editor._worker_list.count() == 0
