# tests/test_s05_soft_no_duty_after_night.py
from __future__ import annotations

import datetime as dt

import pulp

from src.constraints.s05_soft_no_duty_after_night import SoftNoDutyAfterNight
from src.domain.types import ShiftType
from src.optimizer.objective import set_objective_with_penalties


def _sum_penalties(ctx, source="soft_no_duty_after_night") -> float:
    # ctx["penalties"] から該当 source のペナルティ合算
    total = 0.0
    for items in ctx.get("penalties", []):
        if getattr(items, "source", None) != source:
            continue
        v = pulp.value(items.var)
        if v is None:
            continue
        total += float(items.weight) * float(v)
    return total


def _bin(name: str, lb=0, ub=1):
    return pulp.LpVariable(name, lowBound=lb, upBound=ub, cat="Binary")


def test_penalty_for_DAY_after_NIGHT():
    # 前日 NIGHT, 翌日 DAY -> ペナルティ = weight
    d1 = dt.date(2025, 1, 10)
    d2 = dt.date(2025, 1, 11)
    days = [d1, d2]

    x = {}
    x[("H1", "Alice", d1, ShiftType.NIGHT)] = _bin("x_night", lb=1, ub=1)
    x[("H1", "Alice", d2, ShiftType.DAY)] = _bin("x_day", lb=1, ub=1)

    m = pulp.LpProblem("s05_day_after_night", pulp.LpMaximize)
    base_obj = pulp.lpSum(x.values())

    ctx = {"days": days}
    SoftNoDutyAfterNight(weight=0.5).apply(m, x, ctx)
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 0.5) <= 1e-8


def test_penalty_for_AM_after_NIGHT():
    # 前日 NIGHT, 翌日 AM -> ペナルティ = weight
    d1 = dt.date(2025, 2, 1)
    d2 = dt.date(2025, 2, 2)
    days = [d1, d2]

    x = {}
    x[("H1", "Bob", d1, ShiftType.NIGHT)] = _bin("x_night", lb=1, ub=1)
    x[("H2", "Bob", d2, ShiftType.AM)] = _bin("x_am", lb=1, ub=1)

    m = pulp.LpProblem("s05_am_after_night", pulp.LpMaximize)
    base_obj = pulp.lpSum(x.values())

    ctx = {"days": days}
    SoftNoDutyAfterNight(weight=0.8).apply(m, x, ctx)
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 0.8) <= 1e-8


def test_no_penalty_for_PM_or_no_night():
    # PM は対象外, また前日に NIGHT が無い場合も対象外
    # NIGHT -> PM -> 0
    # no NIGHT -> DAY -> 0
    d1 = dt.date(2025, 3, 5)
    d2 = dt.date(2025, 3, 6)
    days = [d1, d2]

    # ケース1: NIGHT -> PM
    x1 = {}
    x1[("H", "Cara", d1, ShiftType.NIGHT)] = _bin("x_night", lb=1, ub=1)
    x1[("H", "Cara", d2, ShiftType.PM)] = _bin("x_pm", lb=1, ub=1)
    m1 = pulp.LpProblem("s05_night_then_pm", pulp.LpMaximize)
    ctx1 = {"days": days}
    SoftNoDutyAfterNight(weight=1.0).apply(m1, x1, ctx1)
    set_objective_with_penalties(m1, pulp.lpSum(x1.values()), ctx1)
    status = m1.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx1) <= 1e-8

    # ケース2: 前日に NIGHT なし
    x2 = {}
    x2[("H", "Dave", d2, ShiftType.DAY)] = _bin("x_day", lb=1, ub=1)
    m2 = pulp.LpProblem("s05_no_prev_night", pulp.LpMaximize)
    ctx2 = {"days": days}
    SoftNoDutyAfterNight(weight=1.0).apply(m2, x2, ctx2)
    set_objective_with_penalties(m2, pulp.lpSum(x2.values()), ctx2)
    status = m2.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx2) <= 1e-8


def test_no_penalty_when_next_day_outside_horizon():
    # days = [d1] のみ -> 翌日が計画範囲外なので 0
    d1 = dt.date(2025, 4, 30)
    days = [d1]

    x = {}
    x[("H", "Eve", d1, ShiftType.NIGHT)] = _bin("x_night", lb=1, ub=1)

    m = pulp.LpProblem("s05_edge", pulp.LpMaximize)
    ctx = {"days": days}
    SoftNoDutyAfterNight(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_multiple_conflicts_sum_over_days_and_workers():
    # 複数 worker と複数日の衝突は独立に加算
    # Alice: d1 NIGHT -> d2 DAY -> 1件
    # Bob: d2 NIGHT -> d3 AM -> 1件
    # 合計 2 * weight
    d1 = dt.date(2025, 5, 1)
    d2 = dt.date(2025, 5, 2)
    d3 = dt.date(2025, 5, 3)
    days = [d1, d2, d3]

    x = {}
    x[("H1", "Alice", d1, ShiftType.NIGHT)] = _bin("x_a_n_d1", lb=1, ub=1)
    x[("H2", "Alice", d2, ShiftType.DAY)] = _bin("x_a_d_d2", lb=1, ub=1)
    x[("H3", "Bob", d2, ShiftType.NIGHT)] = _bin("x_b_n_d2", lb=1, ub=1)
    x[("H4", "Bob", d3, ShiftType.AM)] = _bin("x_b_a_d3", lb=1, ub=1)

    m = pulp.LpProblem("s05_multi", pulp.LpMaximize)
    ctx = {"days": days}
    weight = 0.4
    SoftNoDutyAfterNight(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 2 * weight) <= 1e-8


def test_or_logic_single_penalty_even_if_multiple_next_day_assignments():
    # 翌日に複数の DAY or AM があっても OR 集約のためペナルティは 1 件のみ
    d1 = dt.date(2025, 6, 10)
    d2 = dt.date(2025, 6, 11)
    days = [d1, d2]

    x = {}
    x[("H1", "Frank", d1, ShiftType.NIGHT)] = _bin("x_night", lb=1, ub=1)
    x[("H2", "Frank", d2, ShiftType.DAY)] = _bin("x_day_h2", lb=1, ub=1)
    x[("H3", "Frank", d2, ShiftType.AM)] = _bin("x_am_h3", lb=1, ub=1)
    x[("H4", "Frank", d2, ShiftType.DAY)] = _bin("x_day_h4", lb=1, ub=1)

    m = pulp.LpProblem("s05_or_logic", pulp.LpMaximize)
    ctx = {"days": days}
    weight = 0.9
    SoftNoDutyAfterNight(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - weight) <= 1e-8
