# tests/test_s08_soft_no_consecutive_remote.py
"""s08: is_remote=True の勤務が2日間連続した場合のペナルティをテスト."""

from __future__ import annotations

import datetime as dt

import pulp

from src.constraints.s08_soft_no_consecutive_remote import (
    SoftNoConsecutiveRemote,
)
from src.domain.types import Hospital, ShiftType
from src.optimizer.objective import set_objective_with_penalties

SOURCE = "soft_no_consecutive_remote"


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


H_REMOTE = Hospital(name="Remote", is_remote=True, is_university=False, demand_rules=[])
H_LOCAL = Hospital(name="Local", is_remote=False, is_university=False, demand_rules=[])


# -- ペナルティが発生するケース --


def test_penalty_for_consecutive_remote_days():
    """remote病院にd, d+1ともに勤務 -> ペナルティ."""
    d1 = dt.date(2025, 6, 2)  # Monday
    d2 = dt.date(2025, 6, 3)  # Tuesday
    days = [d1, d2]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_d1", lb=1, ub=1)
    x[("Remote", "Alice", d2, ShiftType.DAY)] = _bin("s08_x_d2", lb=1, ub=1)

    m = pulp.LpProblem("s08_consec_remote", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    SoftNoConsecutiveRemote(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 1.0) <= 1e-8


def test_penalty_for_different_remote_hospitals():
    """異なるremote病院でもd, d+1で勤務 -> ペナルティ."""
    h_remote2 = Hospital(name="Remote2", is_remote=True, is_university=False, demand_rules=[])
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    days = [d1, d2]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_r1", lb=1, ub=1)
    x[("Remote2", "Alice", d2, ShiftType.AM)] = _bin("s08_x_r2", lb=1, ub=1)

    m = pulp.LpProblem("s08_diff_remote", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, h_remote2, H_LOCAL]}
    SoftNoConsecutiveRemote(weight=0.5).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 0.5) <= 1e-8


def test_penalty_for_three_consecutive_remote_days():
    """3日連続remote勤務 -> ペナルティ2件."""
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    d3 = dt.date(2025, 6, 4)
    days = [d1, d2, d3]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_3d1", lb=1, ub=1)
    x[("Remote", "Alice", d2, ShiftType.DAY)] = _bin("s08_x_3d2", lb=1, ub=1)
    x[("Remote", "Alice", d3, ShiftType.DAY)] = _bin("s08_x_3d3", lb=1, ub=1)

    m = pulp.LpProblem("s08_three_days", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    weight = 0.5
    SoftNoConsecutiveRemote(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 2 * weight) <= 1e-8


def test_multiple_workers_independent_penalties():
    """複数workerのremote連続はそれぞれ独立にペナルティ."""
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    days = [d1, d2]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_a1", lb=1, ub=1)
    x[("Remote", "Alice", d2, ShiftType.DAY)] = _bin("s08_x_a2", lb=1, ub=1)
    x[("Remote", "Bob", d1, ShiftType.AM)] = _bin("s08_x_b1", lb=1, ub=1)
    x[("Remote", "Bob", d2, ShiftType.PM)] = _bin("s08_x_b2", lb=1, ub=1)

    m = pulp.LpProblem("s08_multi_worker", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    weight = 0.6
    SoftNoConsecutiveRemote(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 2 * weight) <= 1e-8


def test_or_logic_multiple_remote_shifts_same_day_single_penalty():
    """同日にremote複数シフトでも日ペアあたりペナルティは1件."""
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    days = [d1, d2]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_or1", lb=1, ub=1)
    x[("Remote", "Alice", d1, ShiftType.PM)] = _bin("s08_x_or2", lb=1, ub=1)
    x[("Remote", "Alice", d2, ShiftType.AM)] = _bin("s08_x_or3", lb=1, ub=1)

    m = pulp.LpProblem("s08_or_logic", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    weight = 0.8
    SoftNoConsecutiveRemote(weight=weight).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - weight) <= 1e-8


# -- ペナルティが発生しないケース --


def test_no_penalty_when_local_consecutive():
    """local病院に2日連続勤務 -> ペナルティなし."""
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    days = [d1, d2]

    x = {}
    x[("Local", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_loc1", lb=1, ub=1)
    x[("Local", "Alice", d2, ShiftType.DAY)] = _bin("s08_x_loc2", lb=1, ub=1)

    m = pulp.LpProblem("s08_local", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    SoftNoConsecutiveRemote(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_remote_not_consecutive():
    """remote勤務が連続していない(1日あける) -> ペナルティなし."""
    d1 = dt.date(2025, 6, 2)
    d3 = dt.date(2025, 6, 4)
    days = [d1, dt.date(2025, 6, 3), d3]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_gap1", lb=1, ub=1)
    x[("Remote", "Alice", d3, ShiftType.DAY)] = _bin("s08_x_gap2", lb=1, ub=1)

    m = pulp.LpProblem("s08_gap", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    SoftNoConsecutiveRemote(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_different_workers():
    """remote勤務がd,d+1で別worker -> ペナルティなし."""
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    days = [d1, d2]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_dw1", lb=1, ub=1)
    x[("Remote", "Bob", d2, ShiftType.DAY)] = _bin("s08_x_dw2", lb=1, ub=1)

    m = pulp.LpProblem("s08_diff_worker", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    SoftNoConsecutiveRemote(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_next_day_outside_horizon():
    """翌日が計画範囲外 -> ペナルティなし."""
    d1 = dt.date(2025, 6, 2)
    days = [d1]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_edge", lb=1, ub=1)

    m = pulp.LpProblem("s08_edge", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    SoftNoConsecutiveRemote(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_mixed_remote_local():
    """d=remote, d+1=local -> ペナルティなし."""
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    days = [d1, d2]

    x = {}
    x[("Remote", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_mix1", lb=1, ub=1)
    x[("Local", "Alice", d2, ShiftType.DAY)] = _bin("s08_x_mix2", lb=1, ub=1)

    m = pulp.LpProblem("s08_mixed", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_REMOTE, H_LOCAL]}
    SoftNoConsecutiveRemote(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_no_remote_hospitals():
    """remote病院がない場合 -> ペナルティなし."""
    d1 = dt.date(2025, 6, 2)
    d2 = dt.date(2025, 6, 3)
    days = [d1, d2]

    x = {}
    x[("Local", "Alice", d1, ShiftType.DAY)] = _bin("s08_x_norem1", lb=1, ub=1)
    x[("Local", "Alice", d2, ShiftType.DAY)] = _bin("s08_x_norem2", lb=1, ub=1)

    m = pulp.LpProblem("s08_no_remote", pulp.LpMaximize)
    ctx: dict = {"days": days, "hospitals": [H_LOCAL]}
    SoftNoConsecutiveRemote(weight=1.0).apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8
