import datetime as dt
import importlib
import sys

import pulp
import pytest


def _reset_registry_and_module():
    import src.constraints.base as base

    base.constraint_registry.clear()
    sys.modules.pop("src.constraints.c01_one_person_per_hospital", None)
    importlib.invalidate_caches()


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry_and_module()
    yield
    _reset_registry_and_module()


def test_plugin_registers_on_import():
    from src.constraints.base import all_constraints

    assert all_constraints() == []
    import src.constraints.c01_one_person_per_hospital  # noqa: F401

    names = [c.name for c in all_constraints()]
    assert "one_person_per_hospital" in names


def test_enforces_exactly_one_per_required_day():
    """required_hd に含まれる (h,d) は、合計ちょうど1人になる。"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h = "大学"
    d = dt.date(2025, 10, 9)
    w1, w2 = "診断01", "診断02"

    # 2候補(同病院・同日・別ワーカー)
    x = {
        (h, w1, d, "NIGHT"): pulp.LpVariable("x1", 0, 1, cat="Binary"),
        (h, w2, d, "NIGHT"): pulp.LpVariable("x2", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("one", pulp.LpMinimize)
    ctx = {"required_hd": {(h, d)}}
    constraint.apply(m, x, ctx)

    # スラック変数の最小化を目的関数にする
    slack_vars = list(ctx.get("shortage_slack", {}).values())
    m += pulp.lpSum(slack_vars)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert sum(pulp.value(v) for v in x.values()) == 1  # ちょうど1
    # スラック変数は0になるはず(不足なし)
    assert sum(pulp.value(v) for v in slack_vars) == 0


def test_non_required_day_is_not_constrained():
    """required_hd にない (h,d) には制約が張られない。"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h = "大学"
    d = dt.date(2025, 10, 9)
    w1, w2 = "診断01", "診断02"

    x = {
        (h, w1, d, "NIGHT"): pulp.LpVariable("x1", 0, 1, cat="Binary"),
        (h, w2, d, "NIGHT"): pulp.LpVariable("x2", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("no_constrain", pulp.LpMinimize)
    ctx = {"required_hd": set()}  # 対象外
    constraint.apply(m, x, ctx)

    # 制約が生成されていないことを確認
    assert len(m.constraints) == 0
    # スラック変数も作られていないことを確認
    assert "shortage_slack" not in ctx or len(ctx["shortage_slack"]) == 0

    # 目的関数を設定して解く(制約がないので任意の値を取れる)
    m += 0  # ダミーの目的関数
    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"


def test_infeasible_when_required_but_no_candidates():
    """required_hd に (h,d) があるのに、その日の変数が1つも無い場合、スラック変数で補完される。"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h = "大学"
    d_req = dt.date(2025, 10, 9)
    d_other = dt.date(2025, 10, 10)

    # 変数は d_other のみ(= d_req の候補はゼロ)
    x = {
        (h, "診断01", d_other, "NIGHT"): pulp.LpVariable("x_other", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("shortage", pulp.LpMinimize)
    ctx = {"required_hd": {(h, d_req)}}  # d_req を要求日に指定
    constraint.apply(m, x, ctx)

    # スラック変数の最小化を目的関数にする
    slack_vars = list(ctx.get("shortage_slack", {}).values())
    m += pulp.lpSum(slack_vars)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # 実際の勤務者は0人(d_reqの候補がないため)、スラック変数は1になる(人手不足)
    # d_reqに対応する勤務者変数は存在しないので、自動的に0人
    # 存在するのはd_otherの変数のみ
    req_day_workers = sum(
        pulp.value(v) for (h_var, w_var, d_var, s_var), v in x.items() if d_var == d_req
    )
    assert req_day_workers == 0  # d_reqの勤務者は0人
    assert sum(pulp.value(v) for v in slack_vars) == 1  # 不足分


def test_constraint_names_unique_across_days():
    """制約名が日付でユニークになることを確認。"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h = "大学"
    d1 = dt.date(2025, 10, 9)
    d2 = dt.date(2025, 10, 10)

    x = {
        (h, "A", d1, "NIGHT"): pulp.LpVariable("x1", 0, 1, cat="Binary"),
        (h, "B", d2, "NIGHT"): pulp.LpVariable("x2", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("uniq", pulp.LpMaximize)
    m += pulp.lpSum(x.values())

    ctx = {"required_hd": {(h, d1), (h, d2)}}
    constraint.apply(m, x, ctx)

    names = list(m.constraints.keys())
    assert any(f"one_person_{h}_20251009" in n for n in names)
    assert any(f"one_person_{h}_20251010" in n for n in names)
    assert len({n for n in names if n.startswith(f"one_person_{h}_")}) == 2
