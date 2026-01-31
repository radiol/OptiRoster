"""メインウィンドウ — タブ構成 + Editor 起動のハブ."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.api.types import is_integer_dtype
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.common.paths import Paths
from src.gui.common.window_registry import WindowRegistry
from src.gui.tabs.settings_tab import SettingsTab

# パス集約
_paths = Paths.from_file(__file__)
PROJECT_ROOT = _paths.project_root
CONFIG_DIR = _paths.config_dir
DATA_DIR = _paths.data_dir
HOSPITALS_TOML_PATH = _paths.hospitals_toml
WORKERS_TOML_PATH = _paths.workers_toml
MAX_ASSIGNMENTS_PATH = _paths.max_assignments_csv
SPECIFIED_DATES_PATH = _paths.specified_dates_toml


# -------- ユーティリティ --------
def info(parent: QWidget, msg: str) -> None:
    QMessageBox.information(parent, "情報", msg)


def warn(parent: QWidget, msg: str) -> None:
    QMessageBox.warning(parent, "注意", msg)


def err(parent: QWidget, msg: str) -> None:
    QMessageBox.critical(parent, "エラー", msg)


def coerce_int_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    各列を数値化し、全ての非NAが整数値なら pandas の nullable 整数型(Int64)にする。
    例: 1.0, 2.0, "" -> 1, 2, <NA>
    """
    out = df.copy()
    for c in out.columns:
        s = pd.to_numeric(out[c], errors="coerce")  # 数値以外→NA
        if s.notna().any() and ((s.dropna() % 1) == 0).all():
            out[c] = s.astype("Int64")
    return out


def df_to_table(table: QTableWidget, df: pd.DataFrame) -> None:
    table.clear()
    table.setRowCount(len(df))
    table.setColumnCount(len(df.columns))
    table.setHorizontalHeaderLabels([str(c) for c in df.columns])

    for r in range(len(df)):
        for c in range(len(df.columns)):
            v = df.iat[r, c]
            item = QTableWidgetItem()
            if pd.isna(v):
                item.setText("")
            else:
                dtype = df.dtypes[df.columns[c]]
                is_int_col = is_integer_dtype(dtype)
                try:
                    f = float(v)
                    is_int_like = float(f).is_integer()
                except Exception:
                    is_int_like = False

                if is_int_col or is_int_like:
                    item.setData(Qt.ItemDataRole.DisplayRole, int(float(v)))
                else:
                    item.setText(str(v))

            table.setItem(r, c, item)

    table.resizeColumnsToContents()


def table_to_df(table: QTableWidget) -> pd.DataFrame:
    rows = table.rowCount()
    cols = table.columnCount()
    headers = []
    for c in range(cols):
        header_item = table.horizontalHeaderItem(c)
        if header_item is not None:
            headers.append(header_item.text())
        else:
            headers.append(f"col{c}")
    data = []
    for r in range(rows):
        row = []
        for c in range(cols):
            it = table.item(r, c)
            row.append("" if it is None else it.text())
        data.append(row)
    return pd.DataFrame(data, columns=headers)


# -------- メイン処理タブ --------
class MainTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.input_path: Path | None = None
        self.input_label = QLabel("勤務希望 CSV: (未選択)")
        self.btn_open = QPushButton("勤務希望csv選択")
        self.btn_run = QPushButton("処理実行")
        self.btn_save = QPushButton("勤務表Excel出力")
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        top = QHBoxLayout()
        top.addWidget(self.input_label, 1)
        top.addWidget(self.btn_open)
        top.addWidget(self.btn_run)
        top.addWidget(self.btn_save)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(QLabel("Log:"))
        lay.addWidget(self.table)

        self.btn_open.clicked.connect(self.choose_input)
        self.btn_run.clicked.connect(self.run_process)
        self.btn_save.clicked.connect(self.save_result)

        self.result_df: pd.DataFrame | None = None

    def log_append(self, message: str, color: str | None = None) -> None:
        """ログメッセージをテーブルに追加"""
        current_rows = self.table.rowCount()
        self.table.setRowCount(current_rows + 1)

        import datetime

        from PySide6.QtGui import QColor

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        time_item = QTableWidgetItem(timestamp)
        message_item = QTableWidgetItem(message)

        if color:
            message_item.setForeground(QColor(color))

        if self.table.columnCount() == 0:
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["時刻", "メッセージ"])

        self.table.setItem(current_rows, 0, time_item)
        self.table.setItem(current_rows, 1, message_item)
        self.table.resizeColumnsToContents()
        self.table.scrollToBottom()
        QApplication.processEvents()

    def choose_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "勤務希望 CSV を選択", "", "CSV (*.csv)")
        if not path:
            return
        self.input_path = Path(path)
        self.input_label.setText(f"勤務希望 CSV: {self.input_path}")

    def run_process(self) -> None:
        if not self.input_path:
            warn(self, "勤務希望 CSV を選んでください。")
            return

        try:
            import pulp

            from src.calendar.utils import generate_monthly_dates
            from src.constraints.autoimport import auto_import_all
            from src.constraints.base import all_constraints
            from src.domain.context import Context
            from src.domain.types import Weekday
            from src.io.hospitals_loader import load_hospitals
            from src.io.max_assignments_loader import load_max_assignments_csv
            from src.io.preferences_loader import load_preferences_csv
            from src.io.specified_days_loader import load_specified_days
            from src.io.workers_loader import load_workers
            from src.model.demand import compute_required_hd
            from src.model.variable_builder import VariableBuilder
            from src.optimizer.objective import set_two_stage_objective
            from src.optimizer.penalty_report import (
                _iter_penalty_rows,
            )
            from src.optimizer.solver import solve

            preferences = load_preferences_csv(str(self.input_path))

            if not preferences:
                warn(self, "勤務希望CSVにデータが見つかりません。")
                return

            first_date = next(iter(preferences.keys()))[1]
            year = first_date.year
            month = first_date.month

            self.log_append(f"対象年月: {year}年{month}月")

            if not HOSPITALS_TOML_PATH.exists():
                warn(self, f"病院設定ファイルが見つかりません: {HOSPITALS_TOML_PATH}")
                return
            if not WORKERS_TOML_PATH.exists():
                warn(self, f"勤務者設定ファイルが見つかりません: {WORKERS_TOML_PATH}")
                return
            if not MAX_ASSIGNMENTS_PATH.exists():
                warn(self, f"最大割り当て設定ファイルが見つかりません: {MAX_ASSIGNMENTS_PATH}")
                return
            if not SPECIFIED_DATES_PATH.exists():
                warn(self, f"指定日設定ファイルが見つかりません: {SPECIFIED_DATES_PATH}")
                return

            self.log_append("設定ファイル読み込み中...")

            hospitals = load_hospitals(str(HOSPITALS_TOML_PATH))
            workers = load_workers(str(WORKERS_TOML_PATH))
            specified_days = load_specified_days(str(SPECIFIED_DATES_PATH))
            max_assignments = load_max_assignments_csv(str(MAX_ASSIGNMENTS_PATH))
            days = generate_monthly_dates(year, month)

            self.log_append(
                f"病院数: {len(hospitals)}, 勤務者数: {len(workers)}, 対象日数: {len(days)}"
            )

            self.log_append("最適化変数を生成中...")
            vb = VariableBuilder(hospitals=hospitals, workers=workers, days=days)
            vb.init_all_zero()
            vb.elevate_by_workers(workers)
            vb.restrict_by_hospitals(hospitals, specified_days)
            vb.filter_by_max_assignments(max_assignments)
            x = vb.materialize(name="x")
            required_hd = compute_required_hd(hospitals, days, list(Weekday), specified_days)

            self.log_append("最適化モデルを構築中...")
            model = pulp.LpProblem(f"duty_{year}_{month:02d}", pulp.LpMinimize)
            ctx = Context(
                hospitals=hospitals,
                workers=workers,
                days=days,
                specified_days=specified_days,
                preferences=preferences,
                max_assignments=max_assignments,
                required_hd=required_hd,
                variables=x,
            )

            self.log_append("制約条件を適用中...")
            auto_import_all()
            for c in all_constraints():
                c.apply(model, x, ctx)

            set_two_stage_objective(model, pulp.lpSum([]), ctx)

            self.log_append(f"制約数: {model.numConstraints()}, 変数数: {model.numVariables()}")

            self.log_append("最適化を実行中...")
            res = solve(model, x, ctx, build_objective=False)

            self.log_append(f"最適化完了: {res.status}")
            self.log_append(f"目的関数値: {res.objective_value}")
            self.log_append(f"総ペナルティ: {res.total_penalty}")
            self.log_append(f"総不足人数: {res.total_shortage}")
            self.log_append(f"求解時間: {res.solve_time:.3f}秒")

            if res.is_shortage:
                self.log_append("⚠️ 人員不足が検出されました:", color="#DC143C")
                for (hospital, d), shortage in sorted(res.shortage_slack.items()):
                    self.log_append(
                        f"  {d.isoformat()} {hospital}: {int(shortage)}人不足", color="#DC143C"
                    )

            if res.penalty_by_source:
                self.log_append("ペナルティ詳細:", color="#FF8C00")
                for source, penalty in sorted(res.penalty_by_source.items(), key=lambda kv: -kv[1]):
                    if penalty > 0:
                        self.log_append(f"  {source}: {penalty}", color="#FF8C00")

                self.log_append("制約別ペナルティ詳細:", color="#FF8C00")
                penalty_rows = list(_iter_penalty_rows(ctx))

                from collections import defaultdict

                by_constraint = defaultdict(list)
                for row in penalty_rows:
                    if row["penalty"] and row["penalty"] > 0:
                        by_constraint[row["summary"]].append(row)

                for constraint_name, items in sorted(
                    by_constraint.items(),
                    key=lambda x: sum(item["penalty"] for item in x[1]),
                    reverse=True,
                ):
                    total_penalty = sum(item["penalty"] for item in items)
                    self.log_append(
                        f"  [{constraint_name}] 合計: {total_penalty:.1f}", color="#FF8C00"
                    )

                    sorted_items = sorted(items, key=lambda x: x["penalty"], reverse=True)[:5]
                    for item in sorted_items:
                        meta_str = (
                            ", ".join(f"{k}={v}" for k, v in item["meta"].items())
                            if item["meta"]
                            else ""
                        )
                        var_info = f"{item['var_name']}" + (f" ({meta_str})" if meta_str else "")
                        self.log_append(
                            f"    - {var_info}: {item['penalty']:.1f} ("
                            f"値:{item['value']:.1f} x 重み:{item['weight']:.1f})",
                            color="#FF8C00",
                        )

                    if len(items) > 5:
                        self.log_append(f"    ... 他{len(items) - 5}項目", color="#FF8C00")

            self.result_df = None
            self.solve_result = res
            self.solve_context = ctx
            self.solve_days = days
            self.solve_hospitals = hospitals

            info(self, "処理が完了しました。")

        except Exception as e:
            import traceback

            error_msg = f"処理に失敗しました:\n{e}\n\n{traceback.format_exc()}"
            self.log_append(f"エラー: {e}")
            err(self, error_msg)

    def save_result(self) -> None:
        """結果をExcelファイルに出力"""
        if not hasattr(self, "solve_result") or not self.solve_result:
            warn(self, "保存する結果がありません。先に処理を実行してください。")
            return

        try:
            from datetime import datetime

            first_date = next(iter(self.solve_result.assignment.keys()))[2]
            year = first_date.year
            month = first_date.month
            default_name = f"schedule_{year}_{month:02d}_{datetime.now().strftime('%H%M%S')}.xlsx"

            file_path, _ = QFileDialog.getSaveFileName(
                self, "勤務表を保存", default_name, "Excel files (*.xlsx);;All files (*)"
            )

            if not file_path:
                return

            from src.io.export_excel import export_schedule_to_excel

            shortage_slack = (
                self.solve_result.shortage_slack if self.solve_result.is_shortage else None
            )

            export_schedule_to_excel(
                assignment=self.solve_result.assignment,
                shortage_slack=shortage_slack,
                days=self.solve_days,
                hospital_names=[h.name for h in self.solve_hospitals],
                out_path=file_path,
            )

            self.log_append(f"Excel出力完了: {file_path}")
            info(self, f"勤務表を保存しました:\n{file_path}")

        except Exception as e:
            import traceback

            error_msg = f"Excel出力に失敗しました:\n{e}\n\n{traceback.format_exc()}"
            self.log_append(f"Excel出力エラー: {e}")
            err(self, error_msg)


# -------- メインウィンドウ --------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Duty Generator")

        self._registry = WindowRegistry()
        self._editors = self._registry._windows  # 後方互換(テスト用)

        tabs = QTabWidget()
        tabs.addTab(MainTab(self), "メイン")
        tabs.addTab(SettingsTab(paths=_paths, registry=self._registry, parent=self), "設定")
        self.setCentralWidget(tabs)
        self.resize(1000, 700)

    def open_hospitals_editor(self) -> None:
        """後方互換: test_editor_launcher 用."""
        from src.gui.editors.hospitals_editor import HospitalsEditorWindow

        editor = self._registry.get_or_create("hospitals", HospitalsEditorWindow)
        if editor.current_path is None and HOSPITALS_TOML_PATH.exists():
            editor.open_path(HOSPITALS_TOML_PATH)

    def open_specified_editor(self) -> None:
        """後方互換: test_editor_launcher 用."""
        from src.gui.editors.specified_editor import SpecifiedDatesEditorWindow

        editor = self._registry.get_or_create("specified", SpecifiedDatesEditorWindow)
        if editor.current_path is None and SPECIFIED_DATES_PATH.exists():
            editor.open_path(SPECIFIED_DATES_PATH)
