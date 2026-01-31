"""Editor ウィンドウの多重起動防止レジストリ."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMainWindow


class WindowRegistry:
    """key ごとにウィンドウを1つだけ保持し、多重起動を防止する."""

    def __init__(self) -> None:
        self._windows: dict[str, QMainWindow] = {}

    def get_or_create(self, key: str, factory: Callable[[], QMainWindow]) -> QMainWindow:
        """key に対応するウィンドウを返す。未生成なら factory で生成して show()."""
        window = self._windows.get(key)
        if window is not None:
            window.show()
            window.raise_()
            window.activateWindow()
            return window
        window = factory()
        self._windows[key] = window
        window.show()
        return window

    def close_all(self) -> None:
        """全ウィンドウを close して辞書をクリア."""
        for window in self._windows.values():
            window.close()
        self._windows.clear()
