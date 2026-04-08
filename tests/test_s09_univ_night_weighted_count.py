"""s09: 大学病院当直の重み付き月間上限ソフト制約のテスト."""

from __future__ import annotations

import datetime as dt

import pulp

from src.domain.types import Hospital, ShiftType
from src.optimizer.objective import set_objective_with_penalties

SOURCE = "soft_univ_night_weighted_count"

UNIV = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])
LOCAL = Hospital(name="一般", is_remote=False, is_university=False, demand_rules=[])

# 2025-06-07(土)=休日(weight=2), 2025-06-08(日)=休日(weight=2)
# 2025-06-02(月)=平日(weight=1), 2025-06-03(火)=平日(weight=1)
SAT = dt.date(2025, 6, 7)
SUN = dt.date(2025, 6, 8)
MON = dt.date(2025, 6, 2)


def _sum_penalties(ctx: dict, source: str = SOURCE) -> float:
    total = 0.0
    for item in ctx.get("penalties", []):
        if getattr(item, "source", None) != source:
            continue
        v = pulp.value(item.var)
        if v is None:
            continue
        total += float(item.weight) * float(v)
    return total


def _fixed(name: str, value: int) -> pulp.LpVariable:
    """固定値のLP変数(value=0 or 1)を返す."""
    return pulp.LpVariable(name, lowBound=value, upBound=value, cat="Integer")


# -- ペナルティが発生するケース --


def test_penalty_when_two_holidays_over_limit(ensure_constraint):
    """休日2回(weight=4) -> over=1, penalty=3.0."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (UNIV.name, "Alice", SUN, ShiftType.NIGHT): _fixed("x_sun", 1),
    }
    m = pulp.LpProblem("s09_over", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, SUN], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 3.0) <= 1e-8


def test_penalty_two_units_over(ensure_constraint):
    """休日2回+平日1回(weight=5) -> over=2, penalty=6.0."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (UNIV.name, "Alice", SUN, ShiftType.NIGHT): _fixed("x_sun", 1),
        (UNIV.name, "Alice", MON, ShiftType.NIGHT): _fixed("x_mon", 1),
    }
    m = pulp.LpProblem("s09_over2", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, SUN, MON], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 6.0) <= 1e-8


def test_multiple_workers_independent_penalties(ensure_constraint):
    """複数workerが各自超過 -> それぞれ独立にペナルティ."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    # Alice: 休日2回(weight=4) -> over=1, penalty=3.0
    # Bob: 休日2回(weight=4) -> over=1, penalty=3.0
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("xa_sat", 1),
        (UNIV.name, "Alice", SUN, ShiftType.NIGHT): _fixed("xa_sun", 1),
        (UNIV.name, "Bob", SAT, ShiftType.NIGHT): _fixed("xb_sat", 1),
        (UNIV.name, "Bob", SUN, ShiftType.NIGHT): _fixed("xb_sun", 1),
    }
    m = pulp.LpProblem("s09_multi", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, SUN], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 6.0) <= 1e-8


# -- ペナルティが発生しないケース --


def test_no_penalty_at_limit(ensure_constraint):
    """休日1回(weight=2)+平日1回(weight=1)=3 -> ちょうど上限, ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (UNIV.name, "Alice", MON, ShiftType.NIGHT): _fixed("x_mon", 1),
    }
    m = pulp.LpProblem("s09_limit", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, MON], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_non_university_not_counted(ensure_constraint):
    """非大学病院のNIGHTはカウントされない -> ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    # LOCAL に3回NIGHT -> 大学病院ではないのでカウントされない
    x = {
        (LOCAL.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (LOCAL.name, "Alice", SUN, ShiftType.NIGHT): _fixed("x_sun", 1),
        (LOCAL.name, "Alice", MON, ShiftType.NIGHT): _fixed("x_mon", 1),
    }
    m = pulp.LpProblem("s09_nonuniv", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV, LOCAL], "days": [SAT, SUN, MON], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_no_university_hospitals(ensure_constraint):
    """大学病院がctxに存在しない -> ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (LOCAL.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
    }
    m = pulp.LpProblem("s09_no_univ", pulp.LpMaximize)
    ctx: dict = {"hospitals": [LOCAL], "days": [SAT], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_no_night_vars(ensure_constraint):
    """大学病院のNIGHT変数が存在しない -> エラーなし, ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    # DAY シフトのみ
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.DAY): _fixed("x_day", 1),
    }
    m = pulp.LpProblem("s09_no_night", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8
