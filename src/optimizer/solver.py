from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import pulp

from src.domain.context import Context, VarKey
from src.optimizer.objective import set_objective_with_penalties
from src.optimizer.report import summarize_penalties


@dataclass
class SolveResult:
    status_code: int
    status: str
    objective_value: float | None
    assignment: dict[VarKey, int]  # VarKey(h,w,d,s)->0/1
    # スラック変数関連
    shortage_slack: dict[tuple[str, date], float]  # (hospital, date) -> slack value
    total_shortage: float  # 総スラック量
    is_shortage: bool  # 人手不足があるかどうか
    # ペナルティ関連
    total_penalty: float  # 総ペナルティ
    penalty_by_source: dict[str, float]
    penalty_rows: list[dict[str, Any]]

    num_constraints: int
    num_variables: int
    solve_time: float  # 秒

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def solve(
    model: pulp.LpProblem,
    x: dict[VarKey, pulp.LpVariable],
    ctx: Context,
    *,
    base_objective: pulp.LpAffineExpression | None = None,
    solver: pulp.LpSolver | None = None,
    build_objective: bool = True,
) -> SolveResult:
    """
    モデルを解いて結果を返す総合関数。
    """
    # 目的関数の構築
    if build_objective:
        assert base_objective is not None
        set_objective_with_penalties(model, base_objective, ctx)

    # ソルバー選択
    if solver is None:
        solver = pulp.PULP_CBC_CMD(msg=False)

    # 実行時間計測
    start = time.time()
    status_code = model.solve(solver)
    end = time.time()
    elapsed = end - start

    status = pulp.LpStatus.get(status_code, str(status_code))
    obj_val = None if model.objective is None else float(pulp.value(model.objective))

    # 割当結果を収集
    assignment: dict[VarKey, int] = {}
    for key, var in x.items():
        v = pulp.value(var) or 0
        assignment[key] = round(v)

    # ペナルティ集計
    total_pen, by_src, rows = summarize_penalties(ctx)

    # スラック変数の集計
    shortage_slack_dict = {}
    total_shortage = 0.0
    shortage_slack_vars = ctx.get("shortage_slack", {})

    for (hospital, d), slack_var in shortage_slack_vars.items():
        slack_value = float(pulp.value(slack_var) or 0)
        if slack_value > 1e-6:  # 浮動小数点の精度を考慮
            shortage_slack_dict[(hospital, d)] = slack_value
            total_shortage += slack_value

    is_shortage = total_shortage > 1e-6

    # 制約数・変数数
    num_constraints = len(model.constraints)
    num_variables = len(model.variables())

    return SolveResult(
        status_code=status_code,
        status=status,
        objective_value=obj_val,
        assignment=assignment,
        total_penalty=float(total_pen),
        penalty_by_source=by_src,
        penalty_rows=rows,
        num_constraints=num_constraints,
        num_variables=num_variables,
        solve_time=elapsed,
        shortage_slack=shortage_slack_dict,
        total_shortage=total_shortage,
        is_shortage=is_shortage,
    )
