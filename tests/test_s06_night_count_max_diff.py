from __future__ import annotations

import datetime as dt

import pulp

from src.domain.types import Hospital, ShiftType
from src.optimizer.objective import set_objective_with_penalties


def _s06_penalty_value(ctx) -> float:
    """ctx["penalties"] から s06 由来の実際のペナルティ総和を計算"""
    pen = 0.0
    for var, w, _meta, source in ctx.get("penalties", []):
        if source == "soft_night_count_max_diff":
            pen += w * var.varValue
    return pen


def test_equal_distribution_no_penalty(ensure_constraint):
    """
    2人候補・4日間で, 2回ずつ平等分配 → 最大差=0 ≤ 1なのでペナルティ 0
    """
    c = ensure_constraint("src.constraints.s06_night_count_max_diff", "soft_night_count_max_diff")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    # 平日4日
    days = [dt.date(2025, 10, d) for d in (6, 7, 8, 9)]  # Mon-Thu
    w1, w2 = "W1", "W2"

    x = {}
    for d in days:
        x[(h.name, w1, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w1_{d}", 0, 1, cat="Binary")
        x[(h.name, w2, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w2_{d}", 0, 1, cat="Binary")

    m = pulp.LpProblem("s06_equal", pulp.LpMaximize)

    # 各日ちょうど1人
    for d in days:
        m += x[(h.name, w1, d, ShiftType.NIGHT)] + x[(h.name, w2, d, ShiftType.NIGHT)] == 1

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    base_obj = pulp.lpSum(x.values())
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # 平等分配 (各 2回) なら差=0 ≤ 1でペナルティなし
    assert _s06_penalty_value(ctx) <= 1e-8


def test_one_difference_no_penalty(ensure_constraint):
    """
    2人候補・5日間で, 3回と2回の分配 → 最大差=1なのでペナルティ 0
    """
    c = ensure_constraint("src.constraints.s06_night_count_max_diff", "soft_night_count_max_diff")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    # 平日5日
    days = [dt.date(2025, 10, d) for d in (6, 7, 8, 9, 10)]  # Mon-Fri
    w1, w2 = "W1", "W2"

    x = {}
    for d in days:
        x[(h.name, w1, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w1_{d}", 0, 1, cat="Binary")
        x[(h.name, w2, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w2_{d}", 0, 1, cat="Binary")

    m = pulp.LpProblem("s06_one_diff", pulp.LpMaximize)

    # 各日ちょうど1人
    for d in days:
        m += x[(h.name, w1, d, ShiftType.NIGHT)] + x[(h.name, w2, d, ShiftType.NIGHT)] == 1

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    base_obj = pulp.lpSum(x.values())
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # 3回と2回なら差=1でペナルティなし
    assert _s06_penalty_value(ctx) <= 1e-8


def test_large_difference_incurs_penalty(ensure_constraint):
    """
    2人候補・6日間で, 強制的に4回と2回に分配 → 最大差=2 > 1でペナルティ発生
    """
    c = ensure_constraint("src.constraints.s06_night_count_max_diff", "soft_night_count_max_diff")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    # 平日6日
    days = [dt.date(2025, 10, d) for d in (6, 7, 8, 9, 10, 13)]  # Mon-Fri + Mon
    w1, w2 = "W1", "W2"

    x = {}
    for d in days:
        x[(h.name, w1, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w1_{d}", 0, 1, cat="Binary")
        x[(h.name, w2, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w2_{d}", 0, 1, cat="Binary")

    m = pulp.LpProblem("s06_large_diff", pulp.LpMaximize)

    # 各日ちょうど1人
    for d in days:
        m += x[(h.name, w1, d, ShiftType.NIGHT)] + x[(h.name, w2, d, ShiftType.NIGHT)] == 1

    # ★ 偏りを強制: W1を4日確定 (W2は残り2日)
    for d in days[:4]:
        m += x[(h.name, w1, d, ShiftType.NIGHT)] == 1

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    base_obj = pulp.lpSum(x.values())
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # 4回と2回なら差=2 > 1でペナルティ発生
    pen = _s06_penalty_value(ctx)
    print(f"[Debug] s06 penalty for 2-diff: {pen}")
    assert pen > 1e-6


def test_three_workers_balanced(ensure_constraint):
    """
    3人候補・6日間で, 均等分配 (各 2回) → 最大差=0でペナルティなし
    """
    c = ensure_constraint("src.constraints.s06_night_count_max_diff", "soft_night_count_max_diff")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    # 平日6日
    days = [dt.date(2025, 10, d) for d in (6, 7, 8, 9, 10, 13)]
    w1, w2, w3 = "W1", "W2", "W3"

    x = {}
    for d in days:
        for w in [w1, w2, w3]:
            x[(h.name, w, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_{w}_{d}", 0, 1, cat="Binary")

    m = pulp.LpProblem("s06_three_balanced", pulp.LpMaximize)

    # 各日ちょうど1人
    for d in days:
        m += sum(x[(h.name, w, d, ShiftType.NIGHT)] for w in [w1, w2, w3]) == 1

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    base_obj = pulp.lpSum(x.values())
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # 3人で6日なら各 2回の均等分配が可能, 差=0でペナルティなし
    assert _s06_penalty_value(ctx) <= 1e-8


def test_three_workers_unbalanced(ensure_constraint):
    """
    3人候補・7日間で, 強制的に3-2-2に分配 → 最大差=1でペナルティなし
    """
    c = ensure_constraint("src.constraints.s06_night_count_max_diff", "soft_night_count_max_diff")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    # 平日7日
    days = [dt.date(2025, 10, d) for d in (6, 7, 8, 9, 10, 13, 14)]
    w1, w2, w3 = "W1", "W2", "W3"

    x = {}
    for d in days:
        for w in [w1, w2, w3]:
            x[(h.name, w, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_{w}_{d}", 0, 1, cat="Binary")

    m = pulp.LpProblem("s06_three_unbalanced", pulp.LpMaximize)

    # 各日ちょうど1人
    for d in days:
        m += sum(x[(h.name, w, d, ShiftType.NIGHT)] for w in [w1, w2, w3]) == 1

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    base_obj = pulp.lpSum(x.values())
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # 3人で7日なら最良で3-2-2の分配, 差=1でペナルティなし
    assert _s06_penalty_value(ctx) <= 1e-8


def test_insufficient_candidates_ignored(ensure_constraint):
    """
    候補日が少ない人(min_candidate_nights未満)は制約の対象外になること
    """
    c = ensure_constraint("src.constraints.s06_night_count_max_diff", "soft_night_count_max_diff")

    h = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])

    # 平日4日
    days = [dt.date(2025, 10, d) for d in (6, 7, 8, 9)]
    w1, w2 = "W1", "W2"

    # W1は全4日候補, W2は1日のみ候補 (min_candidate_nights=2未満)
    x = {}
    for d in days:
        x[(h.name, w1, d, ShiftType.NIGHT)] = pulp.LpVariable(f"x_w1_{d}", 0, 1, cat="Binary")

    # W2は1日のみ候補
    x[(h.name, w2, days[0], ShiftType.NIGHT)] = pulp.LpVariable(
        f"x_w2_{days[0]}", 0, 1, cat="Binary"
    )

    m = pulp.LpProblem("s06_insufficient", pulp.LpMaximize)

    # 各日制約なし (W2は候補日が少なく対象外のため)

    ctx = {"hospitals": [h], "penalties": []}
    c.apply(m, x, ctx)
    base_obj = pulp.lpSum(x.values())
    set_objective_with_penalties(m, base_obj, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # W2が対象外なので, 実質的にペナルティ制約は適用されない
    assert _s06_penalty_value(ctx) <= 1e-8
