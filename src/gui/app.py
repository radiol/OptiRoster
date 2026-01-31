import traceback
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
            # 小数部が無い(= すべて整数として表せる)列だけ Int64 へ
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
                # ✅ dtype は位置で取るなら iloc、もしくは列名で参照
                # dtype = df.dtypes.iloc[c]
                dtype = df.dtypes[df.columns[c]]
                is_int_col = is_integer_dtype(dtype)

                # 値自体が整数相当かも判定(小数 1.0 → 1 表示したいケース)
                try:
                    f = float(v)
                    is_int_like = float(f).is_integer()
                except Exception:
                    is_int_like = False

                if is_int_col or is_int_like:
                    # Qt の DisplayRole に int を渡すと綺麗に整数表示されます
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
        self.input_label = QLabel("勤務希望 CSV: (未選択)")  # ← 文言変更
        self.btn_open = QPushButton("勤務希望csv選択")  # ← 文言変更
        self.btn_run = QPushButton("処理実行")
        self.btn_save = QPushButton("勤務表Excel出力")  # ← 文言変更
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

        # 時刻を追加
        import datetime

        from PySide6.QtGui import QColor

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        time_item = QTableWidgetItem(timestamp)
        message_item = QTableWidgetItem(message)

        # 色指定がある場合はテキスト色を設定
        if color:
            message_item.setForeground(QColor(color))

        # 2列のテーブルにする
        if self.table.columnCount() == 0:
            self.table.setColumnCount(2)
            self.table.setHorizontalHeaderLabels(["時刻", "メッセージ"])

        self.table.setItem(current_rows, 0, time_item)
        self.table.setItem(current_rows, 1, message_item)
        self.table.resizeColumnsToContents()

        # 最新行にスクロール
        self.table.scrollToBottom()

        # UIを更新
        QApplication.processEvents()

    def choose_input(self) -> None:
        # CSV のみ選択可能に
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
            # 1. CSV読み込みと年月の特定

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

            # CSVから優先設定を読み込む
            preferences = load_preferences_csv(str(self.input_path))

            # 年月を特定(最初のキーから)
            if not preferences:
                warn(self, "勤務希望CSVにデータが見つかりません。")
                return

            first_date = next(iter(preferences.keys()))[1]
            year = first_date.year
            month = first_date.month

            self.log_append(f"対象年月: {year}年{month}月")

            # 2. 他のローダーを呼び出してデータを集める
            # 必要なファイルの存在確認
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

            # 3. 変数生成
            self.log_append("最適化変数を生成中...")
            vb = VariableBuilder(hospitals=hospitals, workers=workers, days=days)
            vb.init_all_zero()
            vb.elevate_by_workers(workers)
            vb.restrict_by_hospitals(hospitals, specified_days)
            vb.filter_by_max_assignments(max_assignments)
            x = vb.materialize(name="x")
            required_hd = compute_required_hd(hospitals, days, list(Weekday), specified_days)

            # 4. モデル&ctx
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

            # 5. 制約適用
            self.log_append("制約条件を適用中...")
            auto_import_all()
            for c in all_constraints():
                c.apply(model, x, ctx)

            # 6. 目的関数: 2段階最適化
            set_two_stage_objective(model, pulp.lpSum([]), ctx)

            self.log_append(f"制約数: {model.numConstraints()}, 変数数: {model.numVariables()}")

            # 7. 解く
            self.log_append("最適化を実行中...")
            res = solve(model, x, ctx, build_objective=False)

            # 8. 結果をログに表示
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

                # より詳細なペナルティ情報を表示
                self.log_append("制約別ペナルティ詳細:", color="#FF8C00")
                penalty_rows = list(_iter_penalty_rows(ctx))

                # 制約別集計
                from collections import defaultdict

                by_constraint = defaultdict(list)
                for row in penalty_rows:
                    if row["penalty"] and row["penalty"] > 0:
                        by_constraint[row["summary"]].append(row)

                # 各制約について上位項目を表示
                for constraint_name, items in sorted(
                    by_constraint.items(),
                    key=lambda x: sum(item["penalty"] for item in x[1]),
                    reverse=True,
                ):
                    total_penalty = sum(item["penalty"] for item in items)
                    self.log_append(
                        f"  [{constraint_name}] 合計: {total_penalty:.1f}", color="#FF8C00"
                    )

                    # 各制約の上位5項目を表示
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

            # 結果を保存
            self.result_df = None  # Excel出力時に結果を構築
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
            # 保存先を選択
            from datetime import datetime

            # デフォルトファイル名を生成
            first_date = next(iter(self.solve_result.assignment.keys()))[2]
            year = first_date.year
            month = first_date.month
            default_name = f"schedule_{year}_{month:02d}_{datetime.now().strftime('%H%M%S')}.xlsx"

            file_path, _ = QFileDialog.getSaveFileName(
                self, "勤務表を保存", default_name, "Excel files (*.xlsx);;All files (*)"
            )

            if not file_path:
                return

            # Excel出力を実行
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


# -------- 設定タブ（ランチャー） --------
class SettingsTab(QWidget):
    """各設定ファイル用 Editor Window を起動するランチャー."""

    def __init__(self, main_window: "MainWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._main_window = main_window

        self.btn_hospitals = QPushButton("病院設定 (hospitals.toml) を編集")
        self.btn_specified = QPushButton("病院別勤務希望日 (specified-dates.toml) を編集")

        layout = QVBoxLayout(self)
        layout.addWidget(self.btn_hospitals)
        layout.addWidget(self.btn_specified)
        layout.addStretch()

        self.btn_hospitals.clicked.connect(self._main_window.open_hospitals_editor)
        self.btn_specified.clicked.connect(self._main_window.open_specified_editor)


# -------- メインウィンドウ --------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Duty Generator")
        self._editors: dict[str, QMainWindow] = {}

        tabs = QTabWidget()
        tabs.addTab(MainTab(self), "メイン")
        tabs.addTab(SettingsTab(self, self), "設定")
        self.setCentralWidget(tabs)
        self.resize(1000, 700)

    # --- Editor 起動ヘルパー ---
    def _open_editor(self, key: str, factory: type) -> None:
        """key に対応するエディタが未起動なら生成、起動済みなら前面へ."""
        editor = self._editors.get(key)
        if editor is not None:
            editor.show()
            editor.raise_()
            editor.activateWindow()
            return
        editor = factory(parent=None)
        self._editors[key] = editor
        editor.show()

    def open_hospitals_editor(self) -> None:
        from src.gui.editors.hospitals_editor import get_editor_class

        HospitalsEditorWindow = get_editor_class()
        self._open_editor("hospitals", HospitalsEditorWindow)
        editor = self._editors["hospitals"]
        if hasattr(editor, "current_path") and editor.current_path is None:
            if HOSPITALS_TOML_PATH.exists():
                editor.open_path(HOSPITALS_TOML_PATH)

    def open_specified_editor(self) -> None:
        from src.gui.editors.specified_editor import get_editor_class

        SpecifiedDatesEditorWindow = get_editor_class()
        self._open_editor("specified", SpecifiedDatesEditorWindow)
        editor = self._editors["specified"]
        if hasattr(editor, "current_path") and editor.current_path is None:
            if SPECIFIED_DATES_PATH.exists():
                editor.open_path(SPECIFIED_DATES_PATH)


def main() -> None:
    import sys

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
