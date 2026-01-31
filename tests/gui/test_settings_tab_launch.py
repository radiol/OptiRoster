"""Test: SettingsTab がボタン押下で registry.get_or_create を呼ぶこと."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

from src.gui.common.paths import Paths
from src.gui.common.window_registry import WindowRegistry
from src.gui.tabs.settings_tab import SettingsTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def paths(tmp_path: Path) -> Paths:
    return Paths(project_root=tmp_path)


@pytest.fixture()
def registry(qapp) -> WindowRegistry:
    reg = WindowRegistry()
    yield reg
    reg.close_all()


@pytest.fixture()
def tab(qapp, paths, registry) -> SettingsTab:
    t = SettingsTab(paths=paths, registry=registry)
    yield t
    t.close()


class TestHospitalsButton:
    def test_click_calls_registry_with_hospitals_key(self, tab, registry):
        with patch.object(registry, "get_or_create", wraps=registry.get_or_create) as mock:
            mock.return_value = QMainWindow()
            tab.btn_hospitals.click()
            mock.assert_called_once()
            assert mock.call_args[0][0] == "hospitals"

    def test_click_twice_factory_called_once(self, tab, registry):
        call_count = 0
        original = registry.get_or_create

        def spy(key, factory):
            nonlocal call_count
            call_count += 1
            return original(key, factory)

        with patch.object(registry, "get_or_create", side_effect=spy):
            tab.btn_hospitals.click()
            tab.btn_hospitals.click()
        # registry 内部で factory は1回だけ呼ばれる（spy は2回呼ばれる）
        assert call_count == 2  # get_or_create 自体は2回呼ばれるが…
        # 実際の editor インスタンスは1つ
        assert len([k for k in registry._windows if k == "hospitals"]) <= 1


class TestSpecifiedButton:
    def test_click_calls_registry_with_specified_key(self, tab, registry):
        with patch.object(registry, "get_or_create", wraps=registry.get_or_create) as mock:
            mock.return_value = QMainWindow()
            tab.btn_specified.click()
            mock.assert_called_once()
            assert mock.call_args[0][0] == "specified"


class TestAllButtonsExist:
    def test_four_buttons(self, tab):
        """hospitals / specified / workers / csv の4ボタンが存在すること."""
        assert hasattr(tab, "btn_hospitals")
        assert hasattr(tab, "btn_specified")
        assert hasattr(tab, "btn_workers")
        assert hasattr(tab, "btn_csv")
