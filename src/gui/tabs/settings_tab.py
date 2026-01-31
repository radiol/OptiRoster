"""設定タブ — 各 Editor Window を起動するランチャー."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.common.paths import Paths
from src.gui.common.window_registry import WindowRegistry


class SettingsTab(QWidget):
    """ボタン押下で各 Editor Window を WindowRegistry 経由で起動する."""

    def __init__(
        self,
        paths: Paths,
        registry: WindowRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._paths = paths
        self._registry = registry

        self.btn_hospitals = QPushButton("病院設定 (hospitals.toml) を編集")
        self.btn_specified = QPushButton("病院別勤務希望日 (specified-dates.toml) を編集")
        self.btn_workers = QPushButton("勤務者設定 (workers.toml) を編集")
        self.btn_csv = QPushButton("勤務回数上限 (max-assignments.csv) を編集")

        layout = QVBoxLayout(self)
        layout.addWidget(self.btn_hospitals)
        layout.addWidget(self.btn_specified)
        layout.addWidget(self.btn_workers)
        layout.addWidget(self.btn_csv)
        layout.addStretch()

        self.btn_hospitals.clicked.connect(self._open_hospitals)
        self.btn_specified.clicked.connect(self._open_specified)
        self.btn_workers.clicked.connect(self._open_workers)
        self.btn_csv.clicked.connect(self._open_csv)

    # --- editor 起動 ---
    def _open_hospitals(self) -> None:
        from src.gui.editors.hospitals_editor import HospitalsEditorWindow

        editor = self._registry.get_or_create("hospitals", HospitalsEditorWindow)
        if editor.current_path is None and self._paths.hospitals_toml.exists():
            editor.open_path(self._paths.hospitals_toml)

    def _open_specified(self) -> None:
        from src.gui.editors.specified_editor import SpecifiedDatesEditorWindow

        editor = self._registry.get_or_create("specified", SpecifiedDatesEditorWindow)
        if editor.current_path is None and self._paths.specified_dates_toml.exists():
            editor.open_path(self._paths.specified_dates_toml)

    def _open_workers(self) -> None:
        from src.gui.editors.workers_editor import WorkersEditorWindow

        editor = self._registry.get_or_create("workers", WorkersEditorWindow)
        if editor.current_path is None and self._paths.workers_toml.exists():
            editor.open_path(self._paths.workers_toml)

    def _open_csv(self) -> None:
        from src.gui.editors.csv_editor import CsvEditorWindow

        editor = self._registry.get_or_create("csv", CsvEditorWindow)
        if editor.current_path is None and self._paths.max_assignments_csv.exists():
            editor.open_path(self._paths.max_assignments_csv)
