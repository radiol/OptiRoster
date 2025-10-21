import contextlib
import json
import traceback
from pathlib import Path

import pandas as pd
import tomlkit
from pandas.api.types import is_integer_dtype
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# {project_root}/src/gui/app.py から 2 つ上が project_root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
HOSPITALS_TOML_PATH = CONFIG_DIR / "hospitals.toml"
WORKERS_TOML_PATH = CONFIG_DIR / "workers.toml"
DATA_DIR = PROJECT_ROOT / "data"
MAX_ASSIGNMENTS_PATH = DATA_DIR / "max-assignments.csv"
SPECIFIED_DATES_PATH = DATA_DIR / "specified-dates.toml"


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


def backup(path: Path) -> None:
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        bak.write_text(path.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")


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


# -------- 設定編集タブ --------
def _err(parent: QWidget, msg: str) -> None:
    QMessageBox.critical(parent, "エラー", msg)


def _info(parent: QWidget, msg: str) -> None:
    QMessageBox.information(parent, "情報", msg)


class SettingsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # 上部の操作ボタン列(横並び)
        self.btn_open_max = QPushButton("勤務回数上限設定")  # ← 指定の名称
        self.btn_open_dates = QPushButton("病院別勤務希望日設定")
        self.btn_open = QPushButton("設定ファイルを選択(TOML/CSV/JSON)")
        self.btn_save = QPushButton("上書き保存(.bak作成)")

        top = QHBoxLayout()
        top.addWidget(self.btn_open_max)
        top.addWidget(self.btn_open_dates)
        top.addStretch(1)
        top.addWidget(self.btn_open)
        top.addWidget(self.btn_save)

        # 編集領域(CSV は table、TOML/JSON は editor)
        self.table = QTableWidget()
        self.editor = QPlainTextEdit()
        self.table.hide()
        self.editor.hide()

        # テーブル編集機能の設定
        self.setup_table_editing()

        right = QVBoxLayout()
        right.addLayout(top)
        right.addWidget(QLabel("編集領域:"))
        right.addWidget(self.table)
        right.addWidget(self.editor)

        root = QVBoxLayout(self)
        root.addLayout(right)

        # 状態
        self.path: Path | None = None

        # シグナル
        self.btn_open.clicked.connect(self.open_config_dialog)
        self.btn_save.clicked.connect(self.save_config)
        self.btn_open_max.clicked.connect(lambda: self.load_config_from_path(MAX_ASSIGNMENTS_PATH))
        self.btn_open_dates.clicked.connect(
            lambda: self.load_config_from_path(SPECIFIED_DATES_PATH)
        )

    def setup_table_editing(self) -> None:
        """テーブル編集機能をセットアップ"""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        def handle_key_press(event: QKeyEvent) -> bool:
            """キーボードイベントを処理"""
            # Delete または Backspace キーでセルを空にする
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                current_item = self.table.currentItem()
                if current_item is not None:
                    current_item.setText("")
                    return True
            return False

        # イベントフィルターを設定
        from PySide6.QtCore import QObject

        class EventFilter(QObject):
            def __init__(self, table_widget: QTableWidget) -> None:
                super().__init__()
                self.table_widget = table_widget

            def eventFilter(self, obj: QObject, event: QEvent) -> bool:
                if event.type() == QEvent.Type.KeyPress and obj == self.table_widget:
                    from typing import cast

                    from PySide6.QtGui import QKeyEvent

                    return handle_key_press(cast(QKeyEvent, event))
                return False

        self.event_filter = EventFilter(self.table)
        self.table.installEventFilter(self.event_filter)

    # 汎用オープンダイアログ
    def open_config_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "設定ファイルを選択", "", "TOML (*.toml *.tml);;CSV (*.csv);;JSON (*.json)"
        )
        if not path:
            return
        self.load_config_from_path(Path(path))

    # 指定パスを開く(無ければ最小テンプレを用意)
    def load_config_from_path(self, path: Path) -> None:
        try:
            if not path.exists():
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                if path.suffix.lower() == ".csv":
                    tmpl = "Name,HospitalA,HospitalB\n診断01,1,0\n"
                elif path.suffix.lower() in {".toml", ".tml"}:
                    tmpl = (
                        "# 病院別勤務希望日(指定日)サンプル\n"
                        "# [HospitalA]\n"
                        '# dates = ["2025-10-03", "2025-10-17"]\n'
                        "\n"
                    )
                else:
                    tmpl = "{}\n"
                ret = QMessageBox.question(
                    self,
                    "ファイルがありません",
                    f"{path.name} を新規作成しますか?",  # パスは出さない
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if ret == QMessageBox.StandardButton.Yes:
                    path.write_text(tmpl, encoding="utf-8")
                else:
                    return

            self.path = path

            ext = path.suffix.lower()
            if ext == ".csv":
                df = pd.read_csv(path)
                # 整数表示・保存のための型揃え(存在すれば)
                with contextlib.suppress(NameError):
                    df = coerce_int_columns(df)
                df_to_table(self.table, df)
                # Name を行ヘッダに(存在すれば)
                # Note: apply_name_as_row_header function is not implemented
                # try:
                #     apply_name_as_row_header(self.table, df, hide=True, name_col="Name")
                # except NameError:
                #     pass
                self.table.show()
                self.editor.hide()

            elif ext in {".toml", ".tml"}:
                txt = path.read_text(encoding="utf-8")
                tomlkit.parse(txt)  # 構文検証
                self.editor.setPlainText(txt)
                self.editor.show()
                self.table.hide()

            else:  # JSON
                txt = path.read_text(encoding="utf-8")
                json.loads(txt)  # 構文検証
                self.editor.setPlainText(txt)
                self.editor.show()
                self.table.hide()

        except Exception as e:
            _err(self, f"読み込みに失敗しました:\n{e}\n\n{traceback.format_exc()}")

    def save_config(self) -> None:
        if not self.path:
            _err(self, "保存する設定ファイルを先に選んでください。")
            return
        try:
            # .bak 退避
            if self.path.exists():
                bak = self.path.with_suffix(self.path.suffix + ".bak")
                bak.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")

            ext = self.path.suffix.lower()
            if ext == ".csv":
                df = table_to_df(self.table)
                with contextlib.suppress(NameError):
                    df = coerce_int_columns(df)
                df.to_csv(self.path, index=False)

            elif ext in {".toml", ".tml"}:
                txt = self.editor.toPlainText()
                tomlkit.parse(txt)  # 構文検証
                self.path.write_text(txt, encoding="utf-8")

            else:  # JSON
                txt = self.editor.toPlainText()
                json.loads(txt)  # 構文検証
                self.path.write_text(txt, encoding="utf-8")

            _info(self, "保存しました。(.bak を作成)")
        except Exception as e:
            _err(self, f"保存に失敗しました:\n{e}\n\n{traceback.format_exc()}")


# -------- メインウィンドウ --------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Duty Generator")
        tabs = QTabWidget()
        tabs.addTab(MainTab(self), "メイン")
        tabs.addTab(SettingsTab(self), "設定")
        self.setCentralWidget(tabs)
        self.resize(1000, 700)


def main() -> None:
    import sys

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
