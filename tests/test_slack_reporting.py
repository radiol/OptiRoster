import datetime as dt
import importlib
import sys

import pulp
import pytest

from src.constraints.c01_one_person_per_hospital import OnePersonPerHospital
from src.domain.context import Context
from src.optimizer.solver import solve


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


def test_solve_result_contains_slack_info():
    """SolveResultにスラック変数の情報が含まれることをテスト"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401

    # テスト用のモデル設定
    h = "大学"
    d = dt.date(2025, 10, 9)

    # 必要な勤務者変数がない状況(人手不足が発生する)
    x = {}

    model = pulp.LpProblem("shortage_test", pulp.LpMinimize)
    ctx = Context(
        hospitals=[],
        workers=[],
        days=[d],
        specified_days={},
        preferences=[],
        max_assignments={},
        required_hd={(h, d)},
        variables=x,
    )

    # 制約を適用(スラック変数が作られる)
    constraint = OnePersonPerHospital()
    constraint.apply(model, x, ctx)

    # 解く
    result = solve(model, x, ctx, build_objective=False)

    # スラック変数の情報が含まれていることを確認
    assert hasattr(result, "shortage_slack")
    assert hasattr(result, "total_shortage")
    assert hasattr(result, "is_shortage")

    # 人手不足が検出されることを確認
    assert result.is_shortage is True
    assert result.total_shortage == 1.0
    assert len(result.shortage_slack) == 1

    # 具体的な不足情報を確認
    assert (h, d) in result.shortage_slack
    assert result.shortage_slack[(h, d)] == 1.0


def test_solve_result_no_shortage():
    """人手不足がない場合のテスト"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401

    h = "大学"
    d = dt.date(2025, 10, 9)
    w = "診断01"

    # 必要な勤務者変数がある状況
    x = {
        (h, w, d, "NIGHT"): pulp.LpVariable("x1", 0, 1, cat="Binary"),
    }

    model = pulp.LpProblem("no_shortage_test", pulp.LpMinimize)
    ctx = Context(
        hospitals=[],
        workers=[],
        days=[d],
        specified_days={},
        preferences=[],
        max_assignments={},
        required_hd={(h, d)},
        variables=x,
    )

    # 制約を適用
    constraint = OnePersonPerHospital()
    constraint.apply(model, x, ctx)

    # スラック変数を最小化
    slack_vars = list(ctx.get("shortage_slack", {}).values())
    model += pulp.lpSum(slack_vars)

    # 解く
    result = solve(model, x, ctx, build_objective=False)

    # 人手不足がないことを確認
    assert result.is_shortage is False
    assert result.total_shortage == 0.0
    assert len(result.shortage_slack) == 0
