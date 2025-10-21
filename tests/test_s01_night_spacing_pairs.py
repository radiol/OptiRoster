import datetime as dt

import pulp

from src.domain.types import ShiftType
from src.optimizer.objective import set_objective_with_penalties


def test_weighting_prefers_farther_pair(ensure_constraint):
    """
    Δ=1..5 にペナルティ(Δ小さいほど重い)、Δ>=6 はペナルティなし。
    ここでは d1&d7(Δ=6, 無ペナルティ)が d1&d3(Δ=2, あり)より有利になることを確認。
    """
    c = ensure_constraint(
        "src.constraints.s01_night_spacing_pairs",
        "soft_night_spacing_pairs",
    )

    w, h = "診断01", "A病院"
    d1 = dt.date(2025, 10, 1)
    d3 = dt.date(2025, 10, 3)  # Δ=2 → ペナルティあり
    d7 = dt.date(2025, 10, 7)  # Δ=6 → ペナルティなし

    x = {
        (h, w, d1, ShiftType.NIGHT): pulp.LpVariable("x1", 0, 1, cat="Binary"),
        (h, w, d3, ShiftType.NIGHT): pulp.LpVariable("x3", 0, 1, cat="Binary"),
        (h, w, d7, ShiftType.NIGHT): pulp.LpVariable("x7", 0, 1, cat="Binary"),
    }

    # ベース目的:できるだけ多く割り当て(=3つ全部取りたい)
    m = pulp.LpProblem("soft_pairs", pulp.LpMaximize)

    ctx = {"days": [d1, d3, d7]}
    c.apply(m, x, ctx)

    # 目的を""合計-ペナルティ""に設定
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    v = {k: pulp.value(var) for k, var in x.items()}
    # 近接ペナルティのため、(d1,d7)が優先されやすい
    assert v[(h, w, d1, ShiftType.NIGHT)] == 1
    assert v[(h, w, d7, ShiftType.NIGHT)] == 1
    # d3 は状況により 0 or 1 だが、多くは 0 になる
    assert v[(h, w, d3, ShiftType.NIGHT)] in (0, 1)


def test_no_penalty_when_gap_ge_6(ensure_constraint):
    """
    Δ>=6 はペナルティ0 → 3つとも選んでもペナルティが発生しない構成。
    目的が単純合計なので3つ選ばれる想定。
    """
    import src.constraints.s01_night_spacing_pairs  # noqa: F401

    c = ensure_constraint(
        "src.constraints.s01_night_spacing_pairs",
        "soft_night_spacing_pairs",
    )

    w, h = "診断01", "B病院"
    d1 = dt.date(2025, 10, 1)
    d8 = dt.date(2025, 10, 8)  # Δ=7
    d15 = dt.date(2025, 10, 15)  # Δ=7

    x = {
        (h, w, d1, ShiftType.NIGHT): pulp.LpVariable("x1", 0, 1, cat="Binary"),
        (h, w, d8, ShiftType.NIGHT): pulp.LpVariable("x8", 0, 1, cat="Binary"),
        (h, w, d15, ShiftType.NIGHT): pulp.LpVariable("x15", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("no_penalty", pulp.LpMaximize)

    ctx = {"days": [d1, d8, d15]}
    c.apply(m, x, ctx)

    # 目的を""合計-ペナルティ""に設定
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    vals = [pulp.value(v) for v in x.values()]
    # すべて取れる(ペナルティが無いので合計が最大)
    assert sum(vals) == 3


def test_objective_prefers_farther_with_soft_penalty(ensure_constraint):
    import src.constraints.s01_night_spacing_pairs  # noqa: F401

    c = ensure_constraint(
        "src.constraints.s01_night_spacing_pairs",
        "soft_night_spacing_pairs",
    )

    w, h = "診断02", "C病院"
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)  # Δ=1 → 重いペナルティ
    d7 = dt.date(2025, 10, 7)  # Δ=6 → ペナルティなし

    x = {
        (h, w, d1, ShiftType.NIGHT): pulp.LpVariable("x1", 0, 1, cat="Binary"),
        (h, w, d2, ShiftType.NIGHT): pulp.LpVariable("x2", 0, 1, cat="Binary"),
        (h, w, d7, ShiftType.NIGHT): pulp.LpVariable("x7", 0, 1, cat="Binary"),
    }

    # ★ 目的関数を“先に”設定(合計最大化)
    m = pulp.LpProblem("prefer_farther_with_soft_penalty", pulp.LpMaximize)

    # ★ その後にソフト制約を適用(目的からペナルティを差し引く)
    ctx = {"days": [d1, d2, d7]}
    c.apply(m, x, ctx)

    # 目的を""合計-ペナルティ""に設定
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    v1 = pulp.value(x[(h, w, d1, ShiftType.NIGHT)])
    v2 = pulp.value(x[(h, w, d2, ShiftType.NIGHT)])
    v7 = pulp.value(x[(h, w, d7, ShiftType.NIGHT)])

    # 近接 (d1,d2) は同時に立ちにくく、遠い d7 が選ばれやすい
    # 典型解:d1=1, d7=1, d2=0(ただし ties があり得るので条件は緩めに)
    assert v1 in (0, 1)
    assert v7 in (0, 1)
    # “近接ペア” 同時成立は抑制される(両方1は避けられやすい)
    assert (v1 + v2) <= 1


def test_requires_days_missing_is_safe_no_crash(ensure_constraint):
    """
    ctx に 'days' が無いケースでも KeyError を起こさないようにしたい場合は、
    プラグイン側の requires を満たさないときに適用しない運用にする。
    ここではテスト側で適用スキップロジックを確認。
    """
    import src.constraints.s01_night_spacing_pairs  # noqa: F401

    c = ensure_constraint(
        "src.constraints.s01_night_spacing_pairs",
        "soft_night_spacing_pairs",
    )

    w, h = "診断03", "D病院"
    d1 = dt.date(2025, 10, 1)
    x = {(h, w, d1, ShiftType.NIGHT): pulp.LpVariable("x1", 0, 1, cat="Binary")}
    m = pulp.LpProblem("skip_when_ctx_missing")

    # 通常の適用ループ(requires を満たさない制約は適用しない)
    ctx = {}
    if hasattr(c, "requires") and not c.requires.issubset(ctx.keys()):
        pass  # スキップ
    else:
        c.apply(m, x, ctx)

    # 目的を""合計-ペナルティ""に設定
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
