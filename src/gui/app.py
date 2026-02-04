"""GUI 起動スクリプト."""

from src.gui.main_window import MainWindow  # re-export for backward compat

__all__ = ["MainWindow", "main"]


def main() -> None:
    import sys

    from PySide6.QtWidgets import QApplication

    from src.gui.common.ensure_config import ensure_default_files
    from src.gui.common.paths import Paths

    app = QApplication(sys.argv)
    paths = Paths.from_file(__file__)
    ensure_default_files(paths)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
