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


def build_worker_hospital_weekdays(
    workers: list[Worker],
) -> dict[tuple[str, str], list[str]]:
    """Build a mapping of (worker, hospital) -> ordered, deduped short weekday names.

    Short form: first character of each Weekday value (e.g. "月曜" -> "月").
    Multiple assignments for the same (worker, hospital) pair are merged.

    Args:
        workers: List of Worker domain objects.

    Returns:
        Dict mapping (worker_name, hospital_name) to list of short weekday strings.
    """
    _ORDER = ["月", "火", "水", "木", "金", "土", "日"]

    result: dict[tuple[str, str], list[str]] = {}
    for worker in workers:
        for rule in worker.assignments:
            key = (worker.name, rule.hospital)
            if key not in result:
                result[key] = []
            seen = set(result[key])
            for wd in rule.weekdays:
                short = wd.value[0]  # "月曜" -> "月"
                if short not in seen:
                    result[key].append(short)
                    seen.add(short)

    # 月,火,水,木,金,土,日 の順に正規化
    for key in result:
        result[key] = sorted(
            result[key], key=lambda d: _ORDER.index(d) if d in _ORDER else len(_ORDER)
        )
    return result


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
        # hospital -> bool (True = collapsed)
        self._collapsed: dict[str, bool] = {}
        # hospital -> body QWidget
        self._bodies: dict[str, QWidget] = {}
        # (worker, hospital) -> ["月", "金", ...]
        self._worker_weekdays: dict[tuple[str, str], list[str]] = {}

        # --- toolbar ---
        toolbar = QHBoxLayout()
        btn_open = QPushButton("Open")
        btn_save = QPushButton("Save")
        btn_save_as = QPushButton("Save As")
        self.btn_reload = QPushButton("Reload Workers")
        toolbar.addWidget(btn_open)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_save_as)
        toolbar.addWidget(self.btn_reload)
        toolbar.addStretch()
        btn_open.clicked.connect(self._on_open)
        btn_save.clicked.connect(self._on_save)
        btn_save_as.clicked.connect(self._on_save_as)
        self.btn_reload.clicked.connect(self.reload_workers)

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

    def reload_workers(self) -> None:
        """workers.toml を再読み込みして _hw_map を更新する.

        max-assignments の編集内容 (_model) は保持される。
        workers.toml が未設定または存在しない場合は何もしない。
        """
        if self._workers_path is None or not self._workers_path.exists():
            return
        try:
            workers = load_workers(str(self._workers_path))
            self._hw_map = build_hospital_worker_map(workers)
            self._worker_weekdays = build_worker_hospital_weekdays(workers)
            # 折りたたみ状態は既存キーを維持し、新規病院のみ初期化
            for hospital in self._hw_map:
                if hospital not in self._collapsed:
                    self._collapsed[hospital] = not self.has_non_default(hospital)
            self._rebuild_ui()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"workers.toml の再読み込みに失敗:\n{e}")

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
            self._worker_weekdays = build_worker_hospital_weekdays(workers)

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

    def worker_label(self, worker: str, hospital: str) -> str:
        """勤務者の表示ラベルを返す (例: 'IVR01(月,金)')."""
        days = self._worker_weekdays.get((worker, hospital), [])
        if days:
            return f"{worker}({','.join(days)})"
        return worker

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

    def is_collapsed(self, hospital: str) -> bool:
        """指定病院が折りたたまれていれば True."""
        return self._collapsed.get(hospital, False)

    def toggle_collapse(self, hospital: str) -> None:
        """指定病院の折りたたみ状態を反転し、ビューに反映する."""
        self._collapsed[hospital] = not self._collapsed.get(hospital, False)
        body = self._bodies.get(hospital)
        if body is not None:
            body.setVisible(not self._collapsed[hospital])

    # --- private: UI construction ---

    def _rebuild_ui(self) -> None:
        """_hw_map と _model からビューを再構築する."""
        self._button_groups.clear()
        self._bodies.clear()

        # 各病院の折りたたみ初期状態を設定 (設定なし -> 折りたたむ)
        for hospital in self._hw_map:
            if hospital not in self._collapsed:
                self._collapsed[hospital] = not self.has_non_default(hospital)

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
        layout.setSpacing(0)

        non_default = self.has_non_default(hospital)
        collapsed = self._collapsed.get(hospital, not non_default)

        # --- ヘッダ (クリックで折りたたみトグル) ---
        arrow = "▶" if collapsed else "▼"
        header_btn = QPushButton(f"{arrow} {hospital}")
        header_btn.setFlat(True)
        header_btn.setCheckable(False)
        font = header_btn.font()
        font.setBold(non_default)
        header_btn.setFont(font)
        if not non_default:
            header_btn.setStyleSheet("color: gray; text-align: left;")
        else:
            header_btn.setStyleSheet("text-align: left;")
        layout.addWidget(header_btn)

        # --- 勤務者行をまとめる body ウィジェット ---
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        for worker in workers:
            row = self._make_worker_row(worker, hospital)
            body_layout.addWidget(row)
        body.setVisible(not collapsed)
        layout.addWidget(body)

        self._bodies[hospital] = body

        header_btn.clicked.connect(self._make_collapse_handler(hospital, header_btn, body))

        return frame

    def _make_collapse_handler(
        self, hospital: str, header_btn: QPushButton, body: QWidget
    ) -> object:
        def handler() -> None:
            self._collapsed[hospital] = not self._collapsed.get(hospital, False)
            collapsed = self._collapsed[hospital]
            body.setVisible(not collapsed)
            non_default = self.has_non_default(hospital)
            arrow = "▶" if collapsed else "▼"
            header_btn.setText(f"{arrow} {hospital}")
            if not non_default:
                header_btn.setStyleSheet("color: gray; text-align: left;")
            else:
                header_btn.setStyleSheet("text-align: left;")

        return handler

    def _make_worker_row(self, worker: str, hospital: str) -> QWidget:
        """1勤務者分の行ウィジェット (名前 + 4択ボタン) を作成する."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(16, 0, 0, 0)

        name_label = QLabel(self.worker_label(worker, hospital))
        name_label.setMinimumWidth(100)
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
