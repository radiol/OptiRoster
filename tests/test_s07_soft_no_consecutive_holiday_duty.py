# tests/test_s07_soft_no_consecutive_holiday_duty.py
"""s07: 連続する休日に同一workerが勤務した場合のペナルティをテスト."""

from __future__ import annotations

import datetime as dt

import pulp

from src.constraints.s07_soft_no_consecutive_holiday_duty import (
    SoftNoConsecutiveHolidayDuty,
)
from src.domain.types import ShiftType
from src.optimizer.objective import set_objective_with_penalties

SOURCE = "soft_no_consecutive_holiday_duty"


def _sum_penalties(ctx: dict, source: str = SOURCE) -> float:
    total = 0.0
    for items in ctx.get("penalties", []):
        if getattr(items, "source", None) != source:
            continue
        v = pulp.value(items.var)
        if v is None:
            continue
        total += float(items.weight) * float(v)
    return total


def _bin(name: str, lb: int = 0, ub: int = 1) -> pulp.LpVariable:
    return pulp.LpVariable(name, lowBound=lb, upBound=ub, cat="Integer")


# -- ペナルティが発生するケース --


def test_penalty_for_sat_day_sun_night():
    """土曜DAY + 日曜NIGHT -> ペナルティ."""
    sat = dt.date(2025, 6, 7)  # Saturday
    sun = dt.date(2025, 6, 8)  # Sunday
    days = [sat, sun]

    x = {}
    x[("H1", "Alice", sat, ShiftType.DAY)] = _bin("s07_x_day_sat", lb=1, ub=1)
    x[("H1", "Alice", sun, ShiftType.NIGHT)] = _bin("s07_x_night_sun", lb=1, ub=1)

    m = pulp.LpProblem("s07_sat_sun", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 1.0) <= 1e-8


def test_penalty_for_consecutive_holiday_am_pm():
    """土曜AM + 日曜PM -> ペナルティ."""
    sat = dt.date(2025, 6, 7)
    sun = dt.date(2025, 6, 8)
    days = [sat, sun]

    x = {}
    x[("H1", "Alice", sat, ShiftType.AM)] = _bin("x_am", lb=1, ub=1)
    x[("H2", "Alice", sun, ShiftType.PM)] = _bin("x_pm", lb=1, ub=1)

    m = pulp.LpProblem("s07_am_pm", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=0.7).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 0.7) <= 1e-8


def test_three_consecutive_holidays_two_penalties():
    """3連休(土日月祝)で3日とも勤務 -> ペナルティ2件 (土-日, 日-月)."""
    # 2025-09-13(Sat), 14(Sun), 15(Mon=敬老の日) = 3連休
    sat = dt.date(2025, 9, 13)
    sun = dt.date(2025, 9, 14)
    mon = dt.date(2025, 9, 15)  # 敬老の日
    days = [sat, sun, mon]

    x = {}
    x[("H1", "Alice", sat, ShiftType.DAY)] = _bin("x_day_sat", lb=1, ub=1)
    x[("H1", "Alice", sun, ShiftType.NIGHT)] = _bin("x_night_sun", lb=1, ub=1)
    x[("H1", "Alice", mon, ShiftType.AM)] = _bin("x_am_mon", lb=1, ub=1)

    m = pulp.LpProblem("s07_three_days", pulp.LpMaximize)
    ctx: dict = {"days": days}
    weight = 0.5
    SoftNoConsecutiveHolidayDuty(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 2 * weight) <= 1e-8


def test_multiple_workers_independent_penalties():
    """複数workerの衝突は独立に加算."""
    sat = dt.date(2025, 6, 7)
    sun = dt.date(2025, 6, 8)
    days = [sat, sun]

    x = {}
    x[("H1", "Alice", sat, ShiftType.DAY)] = _bin("x_a_day", lb=1, ub=1)
    x[("H1", "Alice", sun, ShiftType.NIGHT)] = _bin("x_a_night", lb=1, ub=1)
    x[("H2", "Bob", sat, ShiftType.AM)] = _bin("x_b_am", lb=1, ub=1)
    x[("H2", "Bob", sun, ShiftType.PM)] = _bin("x_b_pm", lb=1, ub=1)

    m = pulp.LpProblem("s07_multi_worker", pulp.LpMaximize)
    ctx: dict = {"days": days}
    weight = 0.6
    SoftNoConsecutiveHolidayDuty(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 2 * weight) <= 1e-8


def test_or_logic_multiple_shifts_same_day_single_penalty():
    """同日に複数シフトがあっても日ペアあたりペナルティは1件."""
    sat = dt.date(2025, 6, 7)
    sun = dt.date(2025, 6, 8)
    days = [sat, sun]

    x = {}
    x[("H1", "Alice", sat, ShiftType.DAY)] = _bin("x_day_h1", lb=1, ub=1)
    x[("H2", "Alice", sat, ShiftType.AM)] = _bin("x_am_h2", lb=1, ub=1)
    x[("H3", "Alice", sun, ShiftType.NIGHT)] = _bin("x_night_h3", lb=1, ub=1)
    x[("H4", "Alice", sun, ShiftType.PM)] = _bin("x_pm_h4", lb=1, ub=1)

    m = pulp.LpProblem("s07_or_logic", pulp.LpMaximize)
    ctx: dict = {"days": days}
    weight = 0.8
    SoftNoConsecutiveHolidayDuty(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - weight) <= 1e-8


# -- ペナルティが発生しないケース --


def test_no_penalty_when_different_workers_on_each_day():
    """土曜Alice + 日曜Bob -> workerが異なるのでペナルティなし."""
    sat = dt.date(2025, 6, 7)
    sun = dt.date(2025, 6, 8)
    days = [sat, sun]

    x = {}
    x[("H1", "Alice", sat, ShiftType.DAY)] = _bin("x_a_day", lb=1, ub=1)
    x[("H1", "Bob", sun, ShiftType.NIGHT)] = _bin("x_b_night", lb=1, ub=1)

    m = pulp.LpProblem("s07_diff_worker", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_only_next_day_has_duty():
    """土曜(勤務なし) + 日曜(勤務あり) -> ペナルティなし."""
    sat = dt.date(2025, 6, 7)
    sun = dt.date(2025, 6, 8)
    days = [sat, sun]

    x = {}
    # Saturday: no duty
    x[("H1", "Alice", sun, ShiftType.NIGHT)] = _bin("x_night_sun", lb=1, ub=1)

    m = pulp.LpProblem("s07_next_day_only", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_only_one_day_is_holiday():
    """金曜(平日) + 土曜(休日) -> 両日とも休日ではないのでペナルティなし."""
    fri = dt.date(2025, 6, 6)  # Friday
    sat = dt.date(2025, 6, 7)  # Saturday
    days = [fri, sat]

    x = {}
    x[("H1", "Alice", fri, ShiftType.DAY)] = _bin("x_day_fri", lb=1, ub=1)
    x[("H1", "Alice", sat, ShiftType.NIGHT)] = _bin("x_night_sat", lb=1, ub=1)

    m = pulp.LpProblem("s07_fri_sat", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_weekday_consecutive():
    """月曜 + 火曜(どちらも平日) -> ペナルティなし."""
    mon = dt.date(2025, 6, 2)  # Monday
    tue = dt.date(2025, 6, 3)  # Tuesday
    days = [mon, tue]

    x = {}
    x[("H1", "Alice", mon, ShiftType.DAY)] = _bin("x_day_mon", lb=1, ub=1)
    x[("H1", "Alice", tue, ShiftType.DAY)] = _bin("x_day_tue", lb=1, ub=1)

    m = pulp.LpProblem("s07_weekday", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_holiday_but_only_one_day_has_duty():
    """土曜(勤務あり) + 日曜(勤務なし) -> ペナルティなし."""
    sat = dt.date(2025, 6, 7)
    sun = dt.date(2025, 6, 8)
    days = [sat, sun]

    x = {}
    x[("H1", "Alice", sat, ShiftType.DAY)] = _bin("x_day", lb=1, ub=1)
    # Sunday: no duty

    m = pulp.LpProblem("s07_one_day_only", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_next_day_outside_horizon():
    """翌日が計画範囲外 -> ペナルティなし."""
    sat = dt.date(2025, 6, 7)
    days = [sat]

    x = {}
    x[("H1", "Alice", sat, ShiftType.DAY)] = _bin("x_day", lb=1, ub=1)

    m = pulp.LpProblem("s07_edge", pulp.LpMaximize)
    ctx: dict = {"days": days}
    SoftNoConsecutiveHolidayDuty(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8
