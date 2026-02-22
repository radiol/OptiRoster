"""Smoke tests: HospitalsEditorWindow instantiation and open_path."""

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

    def test_open_path_populates_list(self, editor, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert editor.list_hosp.count() == 1
        assert editor.list_hosp.item(0).text() == "TestH"

    def test_window_title_contains_filename(self, editor, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert "h.toml" in editor.windowTitle()

    def test_save_to_produces_valid_toml(self, editor, tmp_path: Path):
        src = tmp_path / "in.toml"
        src.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(src)
        out = tmp_path / "out.toml"
        editor.save_to(out)
        import tomlkit

        parsed = tomlkit.parse(out.read_text(encoding="utf-8"))
        assert "hospitals" in parsed
        assert str(parsed["hospitals"][0]["name"]) == "TestH"
