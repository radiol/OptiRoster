"""Smoke tests: SpecifiedDatesEditorWindow instantiation and open_path."""

from datetime import date
from pathlib import Path

import pytest
import tomlkit
from PySide6.QtWidgets import QApplication, QCalendarWidget

from src.gui.editors.specified_editor import (
    SpecifiedDatesEditorWindow,
    get_default_month,
)

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

    def test_open_path_populates_list(self, editor, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert editor.list_hosp.count() == 1
        assert editor.list_hosp.item(0).text() == "TestH"

    def test_window_title_contains_filename(self, editor, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        assert "s.toml" in editor.windowTitle()

    def test_save_to_produces_valid_toml(self, editor, tmp_path: Path):
        src = tmp_path / "in.toml"
        src.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(src)
        out = tmp_path / "out.toml"
        editor.save_to(out)
        parsed = tomlkit.parse(out.read_text(encoding="utf-8"))
        assert "hospitals" in parsed
        assert str(parsed["hospitals"][0]["name"]) == "TestH"


class TestCalendarSmoke:
    def test_calendar_is_custom_subclass(self, editor):
        # _MonthCalendar is a QCalendarWidget subclass with paintCell override
        assert isinstance(editor._calendar, QCalendarWidget)
        assert type(editor._calendar).__name__ == "_MonthCalendar"

    def test_initial_page_is_next_month(self, editor):
        y, m = get_default_month(date.today())
        assert editor._calendar.yearShown() == y
        assert editor._calendar.monthShown() == m

    def test_open_path_resets_to_next_month(self, editor, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(MINIMAL_TOML, encoding="utf-8")
        editor.open_path(f)
        y, m = get_default_month(date.today())
        assert editor._calendar.yearShown() == y
        assert editor._calendar.monthShown() == m
