"""GUI 起動スクリプト."""

from src.gui.main_window import MainWindow  # re-export for backward compat

__all__ = ["MainWindow", "main"]


def main() -> None:
    import sys

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    icon_path = "img/icon.png"
    app.setWindowIcon(QIcon(icon_path))

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
