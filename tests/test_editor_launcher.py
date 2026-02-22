"""Test: MainWindow のエディタ管理ロジック(辞書による多重起動防止)."""

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.app import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """セッション単位で QApplication を確保."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def main_window(qapp):
    w = MainWindow()
    yield w
    for editor in list(w._editors.values()):
        editor.close()
    w.close()


class TestEditorsDictExists:
    def test_has_editors_dict(self, main_window):
        assert hasattr(main_window, "_editors")
        assert isinstance(main_window._editors, dict)


class TestHospitalsEditorLaunch:
    def test_creates_instance(self, main_window):
        main_window.open_hospitals_editor()
        assert "hospitals" in main_window._editors
        assert main_window._editors["hospitals"] is not None

    def test_same_instance_on_second_call(self, main_window):
        main_window.open_hospitals_editor()
        first = main_window._editors["hospitals"]
        main_window.open_hospitals_editor()
        second = main_window._editors["hospitals"]
        assert first is second


class TestSpecifiedEditorLaunch:
    def test_creates_instance(self, main_window):
        main_window.open_specified_editor()
        assert "specified" in main_window._editors
        assert main_window._editors["specified"] is not None

    def test_same_instance_on_second_call(self, main_window):
        main_window.open_specified_editor()
        first = main_window._editors["specified"]
        main_window.open_specified_editor()
        second = main_window._editors["specified"]
        assert first is second


class TestDifferentEditors:
    def test_hospitals_and_specified_are_different(self, main_window):
        main_window.open_hospitals_editor()
        main_window.open_specified_editor()
        assert main_window._editors["hospitals"] is not main_window._editors["specified"]
