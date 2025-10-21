import pulp

from src.domain.context import Context


def set_two_stage_objective(
    model: pulp.LpProblem, _: pulp.LpAffineExpression, ctx: Context
) -> None:
    """
    2段階最適化の目的関数設定
    stage1. まずスラック(c01)を最小化する=各病院の勤務日に1名の勤務者がいるようにする
    stage2. 次にソフト制約のペナルティを最小化する
    """
    shortage_slack = ctx.get("shortage_slack", {})
    s_list = list(shortage_slack.values()) if isinstance(shortage_slack, dict) else []
    # stage1
    stage1 = pulp.lpSum(s_list) if s_list else pulp.lpSum([])
    # stage2
    # ここでペナルティの倍率を定義(default: 1.0)
    scale = ctx.get(
        "penalty_source_scale",
        {},
    )
    stage2 = 0
    for var, w, _meta, source in ctx.get("penalties", []):
        stage2 += float(scale.get(source, 1.0)) * float(w) * var
    M = 10_000.0
    model.setObjective(stage1 * M + stage2)


def set_objective_with_penalties(
    model: pulp.LpProblem, base_expr: pulp.LpAffineExpression, ctx: Context
) -> None:
    """
    base_expr: 例) pulp.lpSum(x.values()) など“正の報酬側”
    ctx["penalties"] に入っている式をまとめて差し引いて一度だけ model に設定
    """
    # ここでペナルティの倍率を定義(default: 1.0)
    scale = ctx.get(
        "penalty_source_scale",
        {},
    )
    total_penalty = 0
    for var, w, _meta, source in ctx.get("penalties", []):
        total_penalty += float(scale.get(source, 1.0)) * float(w) * var
    model += base_expr - total_penalty
