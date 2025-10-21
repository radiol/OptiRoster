# src/cli/main.py
from __future__ import annotations

import argparse
import json
import pathlib

import pulp
from rich.console import Console
from rich.table import Table

from src import __version__
from src.calendar.utils import generate_monthly_dates
from src.constraints.autoimport import auto_import_all
from src.constraints.base import all_constraints
from src.domain.context import Context
from src.domain.types import Weekday
from src.io.export_excel import export_schedule_to_excel
from src.io.hospitals_loader import load_hospitals
from src.io.max_assignments_loader import load_max_assignments_csv
from src.io.preferences_loader import load_preferences_csv
from src.io.specified_days_loader import load_specified_days
from src.io.workers_loader import load_workers
from src.model.demand import compute_required_hd
from src.model.variable_builder import VariableBuilder
from src.optimizer.objective import set_two_stage_objective
from src.optimizer.penalty_report import print_penalties_rich
from src.optimizer.solver import SolveResult, solve

# config ディレクトリのデフォルト
CONFIG_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "config"
DEFAULT_HOSPITALS = CONFIG_DIR / "hospitals.toml"
DEFAULT_WORKERS = CONFIG_DIR / "workers.toml"
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"
DEFAULT_MAX_ASSIGNMENTS_CSV = DATA_DIR / "max-assignments.csv"


def build_and_solve(
    year: int,
    month: int,
    hospitals_path: pathlib.Path | str,
    workers_path: pathlib.Path | str,
    specified_days_path: pathlib.Path | str,
    preferences_path: pathlib.Path | str,
    max_assignments_path: pathlib.Path | str,
    json_out: bool,
    xlsx: pathlib.Path | str,
) -> None:
    # 1) 入力ロード
    hospitals = load_hospitals(str(hospitals_path))
    workers = load_workers(str(workers_path))
    specified_days = load_specified_days(str(specified_days_path))
    preferences = load_preferences_csv(str(preferences_path))
    max_assignments = load_max_assignments_csv(str(max_assignments_path))
    days = generate_monthly_dates(year, month)

    # 2) 変数生成
    vb = VariableBuilder(hospitals=hospitals, workers=workers, days=days)
    vb.init_all_zero()
    vb.elevate_by_workers(workers)
    vb.restrict_by_hospitals(hospitals, specified_days)
    vb.filter_by_max_assignments(max_assignments)
    x = vb.materialize(name="x")
    required_hd = compute_required_hd(hospitals, days, list(Weekday), specified_days)

    # 3) モデル&ctx
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

    # 4) 制約適用
    auto_import_all()  # constraints 配下のモジュールを全て import して登録
    for c in all_constraints():
        c.apply(model, x, ctx)

    # 5) 目的関数: 2段階最適化(Slack変数を最小化 → ペナルティを最小化)
    set_two_stage_objective(model, pulp.lpSum([]), ctx)

    # 6) 解く
    res = solve(model, x, ctx, build_objective=False)

    # 7) 出力
    if json_out:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print_report_rich(res)
        print_penalties_rich(ctx)

    # 8) Excel 出力(指定があれば)
    if xlsx:
        shortage_slack = res.shortage_slack if res.is_shortage else None
        export_schedule_to_excel(
            assignment=res.assignment,
            shortage_slack=shortage_slack,
            days=days,
            hospital_names=[h.name for h in hospitals],
            out_path=str(xlsx),
        )
        Console().print(f":white_check_mark: Exported to {xlsx}")


def print_report_rich(res: SolveResult) -> None:
    console = Console()
    console.rule("[bold]Solve Result")
    t = Table(show_header=False)
    t.add_row("Status", res.status)
    t.add_row("Objective", str(res.objective_value))
    t.add_row("Total Penalty", str(res.total_penalty))
    t.add_row("Total Shortage", str(res.total_shortage))
    t.add_row("#Constraints", str(res.num_constraints))
    t.add_row("#Variables", str(res.num_variables))
    t.add_row("Solve Time [s]", f"{res.solve_time:.3f}")
    console.print(t)

    if res.is_shortage:
        console.rule("⚠️  [bold red]Staff Shortage Detected")
        shortage_table = Table("Date", "Hospital", "Shortage", style="red")
        for (hospital, d), shortage in sorted(res.shortage_slack.items()):
            shortage_table.add_row(d.isoformat(), hospital, f"{int(shortage)} person(s)")
        console.print(shortage_table)

    if res.penalty_by_source:
        console.rule("[bold]Penalty by Source")
        ts = Table("Source", "Penalty")
        for k, v in sorted(res.penalty_by_source.items(), key=lambda kv: -kv[1]):
            ts.add_row(k, f"{v}")
        console.print(ts)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="勤務表自動生成システム - 病院勤務スケジュールの最適化ツール"
    )

    # Version option
    ap.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"OptiRoster {__version__}",
        help="バージョン情報を表示",
    )

    # Required arguments with short options
    ap.add_argument("-y", "--year", type=int, required=True, help="対象年 (例: 2025)")
    ap.add_argument("-m", "--month", type=int, required=True, help="対象月 (1-12)")
    ap.add_argument(
        "-s",
        "--specified-days",
        type=pathlib.Path,
        required=True,
        help="指定日勤務を記載した toml ファイル",
    )
    ap.add_argument(
        "-p", "--preferences", type=pathlib.Path, required=True, help="勤務希望CSVファイル"
    )

    # Optional arguments with short options
    ap.add_argument(
        "-a",
        "--max-assignments-csv",
        type=pathlib.Path,
        default=DEFAULT_MAX_ASSIGNMENTS_CSV,
        help=f"最大割り当て数を記載したmax-assignments.csv "
        f"(default: {DEFAULT_MAX_ASSIGNMENTS_CSV})",
    )
    ap.add_argument(
        "-H",
        "--hospitals",
        type=pathlib.Path,
        default=DEFAULT_HOSPITALS,
        help=f"病院の設定を記載したhospitals.toml (default: {DEFAULT_HOSPITALS})",
    )
    ap.add_argument(
        "-w",
        "--workers",
        type=pathlib.Path,
        default=DEFAULT_WORKERS,
        help=f"勤務者の設定を記載したworkers.toml (default: {DEFAULT_WORKERS})",
    )
    ap.add_argument(
        "-x",
        "--xlsx",
        type=pathlib.Path,
        help="Excel 出力パス (例: output/schedule_2025_10.xlsx)",
    )
    ap.add_argument("-j", "--json", action="store_true", help="テキストの代わりにJSON形式で出力")
    args = ap.parse_args()

    build_and_solve(
        args.year,
        args.month,
        args.hospitals,
        args.workers,
        args.specified_days,
        args.preferences,
        args.max_assignments_csv,
        args.json,
        args.xlsx,
    )


if __name__ == "__main__":
    main()
