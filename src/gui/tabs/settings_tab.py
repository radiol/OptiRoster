from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.common.paths import Paths
from src.gui.common.window_registry import WindowRegistry


class SettingsTab(QWidget):
    """Launcher for each Editor Window in Settings tab."""

    def __init__(
        self,
        paths: Paths,
        registry: WindowRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._registry = registry

        self.btn_specified = QPushButton("病院別勤務希望日 (specified-dates.toml) を編集")
        self.btn_csv = QPushButton("勤務回数上限 (max-assignments.csv) を編集")
        self.btn_hospitals = QPushButton("病院設定 (hospitals.toml) を編集")
        self.btn_workers = QPushButton("勤務者設定 (workers.toml) を編集")

        monthly_box = self._make_group(
            title="毎月変更する設定",
            description="各病院の勤務指定日、勤務回数上限など、毎月変更する設定を編集します。",
            buttons=[self.btn_specified, self.btn_csv],
        )
        rare_box = self._make_group(
            title="人事異動などがあった際に編集する設定",
            description="人員の変更や病院勤務日の変更があったときに編集します。",
            buttons=[self.btn_hospitals, self.btn_workers],
        )

        root = QGridLayout(self)
        root.addWidget(monthly_box, 0, 0)
        root.addWidget(rare_box, 0, 1)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 1)
        root.setRowStretch(1, 1)

        self.btn_hospitals.clicked.connect(self._open_hospitals)
        self.btn_specified.clicked.connect(self._open_specified)
        self.btn_workers.clicked.connect(self._open_workers)
        self.btn_csv.clicked.connect(self._open_csv)

    def _make_group(self, title: str, description: str, buttons: list[QPushButton]) -> QGroupBox:
        box = QGroupBox(title)
        v = QVBoxLayout(box)

        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        v.addWidget(desc)

        for b in buttons:
            b.setMinimumHeight(36)
            v.addWidget(b)

        v.addStretch(1)
        return box

    # --- editor launch ---
    def _open_hospitals(self) -> None:
        from src.gui.editors.hospitals_editor import HospitalsEditorWindow

        editor = self._registry.get_or_create("hospitals", HospitalsEditorWindow)
        if editor.current_path is None and self._paths.hospitals_toml.exists():
            editor.open_path(self._paths.hospitals_toml)

    def _open_specified(self) -> None:
        from src.gui.editors.specified_editor import SpecifiedDatesEditorWindow

        editor = self._registry.get_or_create("specified", SpecifiedDatesEditorWindow)
        editor.set_hospitals_path(self._paths.hospitals_toml)
        if editor.current_path is None and self._paths.specified_dates_toml.exists():
            editor.open_path(self._paths.specified_dates_toml)

    def _open_workers(self) -> None:
        from src.gui.editors.workers_editor import WorkersEditorWindow

        editor = self._registry.get_or_create("workers", WorkersEditorWindow)
        editor.set_hospitals_path(self._paths.hospitals_toml)
        if editor.current_path is None and self._paths.workers_toml.exists():
            editor.open_path(self._paths.workers_toml)

    def _open_csv(self) -> None:
        from src.gui.editors.csv_editor import CsvEditorWindow

        editor = self._registry.get_or_create("csv", CsvEditorWindow)
        if editor.current_path is None and self._paths.max_assignments_csv.exists():
            editor.open_path(self._paths.max_assignments_csv)
