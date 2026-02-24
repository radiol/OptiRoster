"""Hospital-centric max-assignments editor.

Replaces the flat CSV grid editor with a hospital-grouped view
where each hospital section lists its assignable workers with
a 4-option toggle: unlimited / forbidden / 1 / 2.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.domain.types import Worker
from src.gui.common.base_editor import BaseEditorWindow
from src.io.max_assignments_loader import load_max_assignments_csv
from src.io.max_assignments_writer import dump_max_assignments_csv
from src.io.workers_loader import load_workers

# (value, label) pairs for the 4-option toggle
_OPTIONS: list[tuple[int | None, str]] = [
    (None, "無制限"),
    (0, "勤務なし"),
    (1, "1回"),
    (2, "2回"),
]


def build_hospital_worker_map(workers: list[Worker]) -> dict[str, list[str]]:
    """Build an ordered mapping of hospital -> [worker_name, ...].

    Only worker-hospital pairs defined in workers.toml assignments are included.
    Workers appear in the order they are listed in `workers`.
    Duplicate hospital entries per worker (same hospital, different weekday) are
    deduplicated so each worker appears at most once per hospital.

    Args:
        workers: List of Worker domain objects.

    Returns:
        Dict mapping hospital name to ordered list of worker names.
    """
    result: dict[str, list[str]] = OrderedDict()
    for worker in workers:
        seen_hospitals: set[str] = set()
        for rule in worker.assignments:
            hosp = rule.hospital
            if hosp in seen_hospitals:
                continue
            seen_hospitals.add(hosp)
            if hosp not in result:
                result[hosp] = []
            result[hosp].append(worker.name)
    return result


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------


class HospitalAssignmentEditorWindow(BaseEditorWindow):
    """病院別勤務回数上限エディタ.

    workers.toml を参照して各病院の担当勤務者を表示し、
    [無制限][勤務なし][1回][2回] の4択ボタンで上限を設定する。
    """

    _file_filter = "CSV (*.csv)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("勤務回数上限エディタ")
        self.resize(700, 600)

        self._workers_path: Path | None = None
        # (worker, hospital) -> int | None
        self._model: dict[tuple[str, str], int | None] = {}
        # hospital -> [worker, ...]  (workers.toml から構築)
        self._hw_map: dict[str, list[str]] = {}
        # (worker, hospital) -> QButtonGroup
        self._button_groups: dict[tuple[str, str], QButtonGroup] = {}

        # --- toolbar ---
        toolbar = QHBoxLayout()
        btn_open = QPushButton("Open")
        btn_save = QPushButton("Save")
        btn_save_as = QPushButton("Save As")
        toolbar.addWidget(btn_open)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_save_as)
        toolbar.addStretch()
        btn_open.clicked.connect(self._on_open)
        btn_save.clicked.connect(self._on_save)
        btn_save_as.clicked.connect(self._on_save_as)

        # --- scroll area for hospital sections ---
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._content_widget)

        root_layout = QVBoxLayout()
        root_layout.addLayout(toolbar)
        root_layout.addWidget(scroll)

        central = QWidget()
        central.setLayout(root_layout)
        self.setCentralWidget(central)

    # --- public API ---

    def set_workers_path(self, path: Path) -> None:
        """workers.toml のパスを設定する."""
        self._workers_path = path

    def open_path(self, path: Path) -> None:
        """max-assignments.csv を読み込んでビューを更新する."""
        try:
            self.current_path = path
            self.setWindowTitle(f"勤務回数上限エディタ - {path.name}")

            # workers.toml が未設定の場合は空ビューで終了
            if self._workers_path is None or not self._workers_path.exists():
                self._hw_map = {}
                self._model = {}
                self._rebuild_ui()
                return

            workers = load_workers(str(self._workers_path))
            self._hw_map = build_hospital_worker_map(workers)

            # CSV が存在すれば読み込む、なければ空モデル
            if path.exists() and path.stat().st_size > 0:
                self._model = load_max_assignments_csv(str(path))
            else:
                self._model = {}

            self._rebuild_ui()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"読み込みに失敗:\n{e}")

    def save_to(self, path: Path) -> None:
        """現在のモデルを max-assignments.csv 形式で書き出す."""
        dump_max_assignments_csv(self._model, str(path))
        self.current_path = path
        self.setWindowTitle(f"勤務回数上限エディタ - {path.name}")

    # --- query API (for tests) ---

    def workers_for_hospital(self, hospital: str) -> list[str]:
        """指定病院の担当勤務者リストを返す."""
        return list(self._hw_map.get(hospital, []))

    def get_value(self, worker: str, hospital: str) -> int | None:
        """指定 (worker, hospital) の現在の上限値を返す."""
        return self._model.get((worker, hospital))

    def set_value(self, worker: str, hospital: str, value: int | None) -> None:
        """指定 (worker, hospital) の上限値をプログラムから設定する."""
        self._model[(worker, hospital)] = value
        grp = self._button_groups.get((worker, hospital))
        if grp is not None:
            _update_button_group(grp, value)

    def has_non_default(self, hospital: str) -> bool:
        """病院のいずれかの勤務者に非デフォルト(非 None)の設定があれば True."""
        for worker in self._hw_map.get(hospital, []):
            if self._model.get((worker, hospital)) is not None:
                return True
        return False

    def hospital_count(self) -> int:
        """表示中の病院セクション数を返す."""
        return len(self._hw_map)

    # --- private: UI construction ---

    def _rebuild_ui(self) -> None:
        """_hw_map と _model からビューを再構築する."""
        self._button_groups.clear()

        # 既存ウィジェットを全削除 (stretch を除く)
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for hospital, workers in self._hw_map.items():
            section = self._make_hospital_section(hospital, workers)
            # stretch の直前に挿入
            self._content_layout.insertWidget(self._content_layout.count() - 1, section)

    def _make_hospital_section(self, hospital: str, workers: list[str]) -> QFrame:
        """1病院分のセクションウィジェットを作成する."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)

        non_default = self.has_non_default(hospital)

        # --- ヘッダ ---
        header = QLabel(hospital)
        font = header.font()
        font.setBold(non_default)
        header.setFont(font)
        if not non_default:
            header.setStyleSheet("color: gray;")
        layout.addWidget(header)

        # --- 勤務者行 ---
        for worker in workers:
            row = self._make_worker_row(worker, hospital)
            layout.addWidget(row)

        return frame

    def _make_worker_row(self, worker: str, hospital: str) -> QWidget:
        """1勤務者分の行ウィジェット (名前 + 4択ボタン) を作成する."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(16, 0, 0, 0)

        name_label = QLabel(worker)
        name_label.setMinimumWidth(80)
        name_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        h.addWidget(name_label)

        current_value = self._model.get((worker, hospital))
        grp = QButtonGroup(row)
        grp.setExclusive(True)

        for btn_value, label in _OPTIONS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(btn_value == current_value)
            btn.setMinimumWidth(60)
            grp.addButton(btn)
            h.addWidget(btn)
            # capture btn_value in closure
            btn.clicked.connect(self._make_toggle_handler(worker, hospital, btn_value))

        h.addStretch()
        self._button_groups[(worker, hospital)] = grp
        return row

    def _make_toggle_handler(self, worker: str, hospital: str, value: int | None) -> object:
        def handler(checked: bool) -> None:
            if checked:
                self._model[(worker, hospital)] = value

        return handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _update_button_group(grp: QButtonGroup, value: int | None) -> None:
    """QButtonGroup のチェック状態を value に合わせて更新する."""
    for btn in grp.buttons():
        # ボタンのテキストから対応する値を逆引き
        btn_value = _label_to_value(btn.text())
        btn.setChecked(btn_value == value)


def _label_to_value(label: str) -> int | None:
    for v, lbl in _OPTIONS:
        if lbl == label:
            return v
    return None
