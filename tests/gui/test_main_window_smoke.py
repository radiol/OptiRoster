"""Smoke tests: MainWindow の生成と基本構造."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget

from src.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def win(qapp):
    w = MainWindow()
    yield w
    w._registry.close_all()
    w.close()


class TestMainWindowSmoke:
    def test_can_instantiate(self, win):
        assert win is not None

    def test_has_registry(self, win):
        from src.gui.common.window_registry import WindowRegistry

        assert isinstance(win._registry, WindowRegistry)

    def test_has_two_tabs(self, win):
        tabs = win.centralWidget()
        assert isinstance(tabs, QTabWidget)
        assert tabs.count() == 2

    def test_tab_labels(self, win):
        tabs = win.centralWidget()
        assert tabs.tabText(0) == "メイン"
        assert tabs.tabText(1) == "設定"

    def test_settings_tab_is_from_tabs_module(self, win):
        from src.gui.tabs.settings_tab import SettingsTab

        tabs = win.centralWidget()
        assert isinstance(tabs.widget(1), SettingsTab)
