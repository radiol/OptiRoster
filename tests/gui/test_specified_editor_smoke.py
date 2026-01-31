"""Smoke tests: SpecifiedDatesEditorWindow の生成と open_path."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.editors.specified_editor import SpecifiedDatesEditorWindow

MINIMAL_TOML = """\
[[hospitals]]
name = "TestH"
dates = [1, 15]
"""


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def editor(qapp):
    w = SpecifiedDatesEditorWindow()
    yield w
    w.close()


class TestSpecifiedEditorSmoke:
    def test_can_instantiate(self, editor):
        assert editor is not None
        assert editor.current_path is None

    def test_open_path_sets_current_path(self, editor, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert editor.current_path == f

    def test_open_path_populates_text(self, editor, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert "TestH" in editor._text_edit.toPlainText()

    def test_window_title_contains_filename(self, editor, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert "s.toml" in editor.windowTitle()
