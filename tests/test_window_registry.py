"""Tests for src.gui.common.window_registry — WindowRegistry."""

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

from src.gui.common.window_registry import WindowRegistry


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def registry(qapp):
    reg = WindowRegistry()
    yield reg
    reg.close_all()


class TestGetOrCreate:
    def test_factory_called_once(self, registry):
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return QMainWindow()

        registry.get_or_create("ed", factory)
        registry.get_or_create("ed", factory)
        assert call_count == 1

    def test_returns_same_instance(self, registry):
        w = QMainWindow()
        first = registry.get_or_create("ed", lambda: w)
        second = registry.get_or_create("ed", lambda: QMainWindow())
        assert first is second

    def test_different_keys_different_instances(self, registry):
        a = registry.get_or_create("a", QMainWindow)
        b = registry.get_or_create("b", QMainWindow)
        assert a is not b


class TestCloseAll:
    def test_close_all_clears_registry(self, registry):
        registry.get_or_create("x", QMainWindow)
        registry.close_all()
        # factory should be called again after close_all
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return QMainWindow()

        registry.get_or_create("x", factory)
        assert call_count == 1
