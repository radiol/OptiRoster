# tests/test_s04_soft_balance_non_night_by_weekday.py
from __future__ import annotations

import datetime as dt

import pulp

from src.domain.types import Hospital, ShiftType
from src.optimizer.objective import set_objective_with_penalties


def _sum_penalties(ctx, source="soft_non_night_balance_by_weekday") -> float:
    """penalties から該当 source のペナルティ合算"""
    total = 0.0
    for items in ctx.get("penalties"):
        if items.source != source:
            continue
        v = pulp.value(items.var)
        if v is None:
            continue
        total += float(items.weight) * float(v)
    return total


def test_balance_two_mondays_day_no_penalty(ensure_constraint):
    """
    同一病院 x 月曜 x DAY が2回、候補2人 → 平均A=1、L=U=1。
    1-1 に割れれば over/under は立たない → ペナルティ0。
    """
    c = ensure_constraint(
        "src.constraints.s04_soft_balance_non_night_by_weekday",
        "soft_non_night_balance_by_weekday",
    )

    h = Hospital(name="病院A", is_remote=False, is_university=False, demand_rules=[])
    # 2025-10-06(月), 2025-10-13(月)
    d1 = dt.date(2025, 10, 6)
    d2 = dt.date(2025, 10, 13)
    w1, w2 = "W1", "W2"

    x = {
        (h.name, w1, d1, ShiftType.DAY): pulp.LpVariable("x_w1_d1", 0, 1, cat="Binary"),
        (h.name, w2, d1, ShiftType.DAY): pulp.LpVariable("x_w2_d1", 0, 1, cat="Binary"),
        (h.name, w1, d2, ShiftType.DAY): pulp.LpVariable("x_w1_d2", 0, 1, cat="Binary"),
        (h.name, w2, d2, ShiftType.DAY): pulp.LpVariable("x_w2_d2", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("s04_balance_ok", pulp.LpMaximize)
    # 各日1名
    m += x[(h.name, w1, d1, ShiftType.DAY)] + x[(h.name, w2, d1, ShiftType.DAY)] == 1
    m += x[(h.name, w1, d2, ShiftType.DAY)] + x[(h.name, w2, d2, ShiftType.DAY)] == 1

    ctx = {"hospitals": [h]}
    c.apply(m, x, ctx)
    # ベースは割当最大化(= 2)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # 典型解は W1@d1, W2@d2 など → 1-1 でペナルティ0
    assert _sum_penalties(ctx) <= 1e-8


def test_skew_two_mondays_day_has_penalty(ensure_constraint):
    """
    同一病院 x 月曜 x DAY が2回、候補2人 → A=1, L=U=1。
    W1 を2回とも固定すると 2-0 → over(W1)>=1, under(W2)>=1 → ペナルティ>0。
    """
    c = ensure_constraint(
        "src.constraints.s04_soft_balance_non_night_by_weekday",
        "soft_non_night_balance_by_weekday",
    )

    h = Hospital(name="病院A", is_remote=False, is_university=False, demand_rules=[])
    d1 = dt.date(2025, 10, 6)  # Mon
    d2 = dt.date(2025, 10, 13)  # Mon
    w1, w2 = "W1", "W2"

    x = {
        (h.name, w1, d1, ShiftType.DAY): pulp.LpVariable("x_w1_d1", 0, 1, cat="Binary"),
        (h.name, w2, d1, ShiftType.DAY): pulp.LpVariable("x_w2_d1", 0, 1, cat="Binary"),
        (h.name, w1, d2, ShiftType.DAY): pulp.LpVariable("x_w1_d2", 0, 1, cat="Binary"),
        (h.name, w2, d2, ShiftType.DAY): pulp.LpVariable("x_w2_d2", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("s04_balance_skew", pulp.LpMaximize)
    # 各日1名
    m += x[(h.name, w1, d1, ShiftType.DAY)] + x[(h.name, w2, d1, ShiftType.DAY)] == 1
    m += x[(h.name, w1, d2, ShiftType.DAY)] + x[(h.name, w2, d2, ShiftType.DAY)] == 1
    # 偏りを強制:W1 を両日固定 → 2-0
    m += x[(h.name, w1, d1, ShiftType.DAY)] == 1
    m += x[(h.name, w1, d2, ShiftType.DAY)] == 1

    ctx = {"hospitals": [h]}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    assert _sum_penalties(ctx) > 1e-6


def test_min_candidate_filter_excludes_sparse_worker(ensure_constraint):
    """
    min_candidate=2 のデフォルト動作確認。
    (h,Mon,DAY) バケツで W1 の候補は2回, W2の候補は1回のみ→ W2は Wh から除外。
    Kh<=1 となり、そのバケツには均一化ペナルティは課されない(=0)。
    """
    # モジュール側 __init__(min_candidate=2) の既定を使う前提
    c = ensure_constraint(
        "src.constraints.s04_soft_balance_non_night_by_weekday",
        "soft_non_night_balance_by_weekday",
    )

    h = Hospital(name="病院A", is_remote=False, is_university=False, demand_rules=[])
    # 2つの月曜(バケツは Mon x DAY)
    d1 = dt.date(2025, 10, 6)  # Mon
    d2 = dt.date(2025, 10, 13)  # Mon
    w1, w2 = "W1", "W2"

    # W1 は2回候補、W2は 1回だけ(d1 のみ候補)
    x = {
        (h.name, w1, d1, ShiftType.DAY): pulp.LpVariable("x_w1_d1", 0, 1, cat="Binary"),
        (h.name, w1, d2, ShiftType.DAY): pulp.LpVariable("x_w1_d2", 0, 1, cat="Binary"),
        (h.name, w2, d1, ShiftType.DAY): pulp.LpVariable("x_w2_d1", 0, 1, cat="Binary"),
        # (h.name, w2, d2, ShiftType.DAY) は候補なし
    }

    m = pulp.LpProblem("s04_min_cand_filter", pulp.LpMaximize)
    # 各日1名(d2 は W1 しか候補が無いので自動的に W1)
    m += x[(h.name, w1, d1, ShiftType.DAY)] + x[(h.name, w2, d1, ShiftType.DAY)] == 1
    m += x[(h.name, w1, d2, ShiftType.DAY)] == 1

    ctx = {"hospitals": [h]}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # W2 は min_candidate(=2) を満たさないため Wh から外れ、Kh<=1 でスキップ → ペナルティ0
    assert _sum_penalties(ctx) <= 1e-8
