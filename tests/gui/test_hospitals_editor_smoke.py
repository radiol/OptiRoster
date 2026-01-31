"""Smoke tests: HospitalsEditorWindow の生成と open_path."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.editors.hospitals_editor import HospitalsEditorWindow

MINIMAL_TOML = """\
[[hospitals]]
name = "TestH"
is_remote = false
is_university = false

[[hospitals.shifts]]
shift_type = "日勤"
weekdays = ["月曜"]
frequency = "毎週"
"""


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def editor(qapp):
    w = HospitalsEditorWindow()
    yield w
    w.close()


class TestHospitalsEditorSmoke:
    def test_can_instantiate(self, editor):
        assert editor is not None
        assert editor.current_path is None

    def test_open_path_sets_current_path(self, editor, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert editor.current_path == f

    def test_open_path_populates_text(self, editor, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert "TestH" in editor._text_edit.toPlainText()

    def test_window_title_contains_filename(self, editor, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert "h.toml" in editor.windowTitle()
