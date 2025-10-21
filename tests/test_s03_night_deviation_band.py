from __future__ import annotations

import datetime as dt
import math

import pulp

from src.domain.types import Hospital, ShiftType
from src.optimizer.objective import set_objective_with_penalties


def _s03_penalty_value(ctx) -> float:
    """ctx["penalties"] から s03 由来の実際のペナルティ総和を計算"""
    pen = 0.0
    for var, w, _meta, source in ctx.get("penalties", []):
        if source == "soft_night_deviation_band":
            pen += w * var.varValue
    return pen


def test_two_weekdays_balance_no_penalty(ensure_constraint):
    """
    平日2日・候補2人 → 平均=1、各1回ずつでペナルティ0になること。
    """
    c = ensure_constraint("src.constraints.s03_night_deviation_band", "soft_night_deviation_band")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    d1 = dt.date(2025, 10, 6)  # Mon
    d2 = dt.date(2025, 10, 7)  # Tue
    w1, w2 = "W1", "W2"

    x = {
        (h.name, w1, d1, ShiftType.NIGHT): pulp.LpVariable("x_w1_d1", 0, 1, cat="Binary"),
        (h.name, w2, d1, ShiftType.NIGHT): pulp.LpVariable("x_w2_d1", 0, 1, cat="Binary"),
        (h.name, w1, d2, ShiftType.NIGHT): pulp.LpVariable("x_w1_d2", 0, 1, cat="Binary"),
        (h.name, w2, d2, ShiftType.NIGHT): pulp.LpVariable("x_w2_d2", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("s03_weekdays", pulp.LpMaximize)
    m += x[(h.name, w1, d1, ShiftType.NIGHT)] + x[(h.name, w2, d1, ShiftType.NIGHT)] == 1
    m += x[(h.name, w1, d2, ShiftType.NIGHT)] + x[(h.name, w2, d2, ShiftType.NIGHT)] == 1

    ctx = {"hospitals": [h], "penalties": []}

    c.apply(m, x, ctx)
    base_obj = pulp.lpSum(x.values())
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _s03_penalty_value(ctx) <= 1e-8
    assert math.isclose(
        pulp.value(x[(h.name, w1, d1, ShiftType.NIGHT)])
        + pulp.value(x[(h.name, w2, d1, ShiftType.NIGHT)]),
        1.0,
    )


def test_weekend_weighting_targets_two_each_no_penalty(ensure_constraint):
    """
    Fri(1.0)+Sat(1.5)+Sun(1.5)+Mon(1.0)=5.0 → 平均2.5。2~3収まればペナルティ0。
    """
    c = ensure_constraint("src.constraints.s03_night_deviation_band", "soft_night_deviation_band")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    d_fri = dt.date(2025, 10, 3)
    d_sat = dt.date(2025, 10, 4)
    d_sun = dt.date(2025, 10, 5)
    d_mon = dt.date(2025, 10, 6)
    w1, w2 = "W1", "W2"

    x = {
        (h.name, w1, d_fri, ShiftType.NIGHT): pulp.LpVariable("x1_fri", 0, 1, cat="Binary"),
        (h.name, w2, d_fri, ShiftType.NIGHT): pulp.LpVariable("x2_fri", 0, 1, cat="Binary"),
        (h.name, w1, d_sat, ShiftType.NIGHT): pulp.LpVariable("x1_sat", 0, 1, cat="Binary"),
        (h.name, w2, d_sat, ShiftType.NIGHT): pulp.LpVariable("x2_sat", 0, 1, cat="Binary"),
        (h.name, w1, d_sun, ShiftType.NIGHT): pulp.LpVariable("x1_sun", 0, 1, cat="Binary"),
        (h.name, w2, d_sun, ShiftType.NIGHT): pulp.LpVariable("x2_sun", 0, 1, cat="Binary"),
        (h.name, w1, d_mon, ShiftType.NIGHT): pulp.LpVariable("x1_mon", 0, 1, cat="Binary"),
        (h.name, w2, d_mon, ShiftType.NIGHT): pulp.LpVariable("x2_mon", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("s03_weekend", pulp.LpMaximize)
    m += x[(h.name, w1, d_fri, ShiftType.NIGHT)] + x[(h.name, w2, d_fri, ShiftType.NIGHT)] == 1
    m += x[(h.name, w1, d_sat, ShiftType.NIGHT)] + x[(h.name, w2, d_sat, ShiftType.NIGHT)] == 1
    m += x[(h.name, w1, d_sun, ShiftType.NIGHT)] + x[(h.name, w2, d_sun, ShiftType.NIGHT)] == 1
    m += x[(h.name, w1, d_mon, ShiftType.NIGHT)] + x[(h.name, w2, d_mon, ShiftType.NIGHT)] == 1

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _s03_penalty_value(ctx) <= 1e-8


def test_forced_skew_incurs_penalty_with_6_days(ensure_constraint):
    c = ensure_constraint("src.constraints.s03_night_deviation_band", "soft_night_deviation_band")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    # 平日10日 → T=10, K=2 → A=5, バンド [5,6]
    days = [dt.date(2025, 10, d) for d in (6, 7, 8, 9, 10, 14, 15, 16, 17, 20)]  # 全て平日
    w1, w2 = "W1", "W2"

    # 両者に十分な候補(各10日)を与える
    x = {}
    for d in days:
        x[(h.name, w1, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w1_{d}", 0, 1, cat="Binary")
        x[(h.name, w2, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w2_{d}", 0, 1, cat="Binary")

    m = pulp.LpProblem("s03_skew_6days", pulp.LpMaximize)

    # 各日ちょうど1人
    for d in days:
        m += x[(h.name, w1, d, ShiftType.NIGHT)] + x[(h.name, w2, d, ShiftType.NIGHT)] == 1

    # ★ 偏りを強制:W1 を 6日確定(W2 は残り4日に押し出される)
    for d in days[:6]:
        m += x[(h.name, w1, d, ShiftType.NIGHT)] == 1

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    print(f"[Debug] Total penalty: {_s03_penalty_value(ctx)}")

    # 平均5のバンド[5,6]から 6-4 は外れる → ペナルティ > 0
    pen = _s03_penalty_value(ctx)
    assert pen > 1e-6
