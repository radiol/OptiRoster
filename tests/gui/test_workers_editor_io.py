"""IO roundtrip tests for WorkersEditorWindow."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.editors.workers_editor import (
    WorkersEditorWindow,
    dump_workers_toml,
    load_workers_toml,
)

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


class TestLoadDumpRoundTrip:
    def test_load_returns_list(self, tmp_path: Path):
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        model = load_workers_toml(f)
        assert isinstance(model, list)
        assert len(model) == 2

    def test_load_first_worker_fields(self, tmp_path: Path):
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        model = load_workers_toml(f)
        w = model[0]
        assert w["name"] == "診断01"
        assert w["is_diagnostic_specialist"] is True
        assert len(w["assignments"]) == 1
        a = w["assignments"][0]
        assert a["hospital"] == "病院1"
        assert a["weekdays"] == ["月曜", "火曜"]
        assert a["shift_type"] == "日勤"

    def test_dump_and_reload_preserves_data(self, tmp_path: Path):
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        model = load_workers_toml(f)
        out = tmp_path / "out.toml"
        dump_workers_toml(model, out)
        reloaded = load_workers_toml(out)
        assert len(reloaded) == len(model)
        for orig, rl in zip(model, reloaded):
            assert orig["name"] == rl["name"]
            assert orig["is_diagnostic_specialist"] == rl["is_diagnostic_specialist"]
            assert len(orig["assignments"]) == len(rl["assignments"])

    def test_worker_without_assignments(self, tmp_path: Path):
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        model = load_workers_toml(f)
        assert model[1]["assignments"] == []


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
        reloaded = load_workers_toml(out)
        assert len(reloaded) == 2
        assert reloaded[0]["name"] == "診断01"
        assert reloaded[1]["name"] == "診断02"

    def test_load_workers_compatibility(self, editor, tmp_path: Path):
        """Saved file must be loadable by the existing load_workers()."""
        src = tmp_path / "in.toml"
        src.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(src)
        out = tmp_path / "out.toml"
        editor.save_to(out)
        from src.io.workers_loader import load_workers

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
