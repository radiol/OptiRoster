import importlib
import sys

import pulp
import pytest

from src.domain.context import Context
from src.optimizer.penalty_report import _get_constraint_summary, _iter_penalty_rows


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


def test_get_constraint_summary():
    """制約のsummaryが正しく取得できることをテスト"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401

    # summary取得をテスト
    summary = _get_constraint_summary("one_person_per_hospital")
    assert summary == "必要な(病院, 日)ごとに勤務者は1人"

    # 存在しない制約名の場合はsource名を返す
    unknown_summary = _get_constraint_summary("unknown_constraint")
    assert unknown_summary == "unknown_constraint"


def test_iter_penalty_rows_with_summary():
    """ペナルティ行のイテレーションでsummaryが含まれることをテスト"""
    import src.constraints.c01_one_person_per_hospital  # noqa: F401

    # テスト用のペナルティ変数
    penalty_var = pulp.LpVariable("test_penalty", 0, 1, cat="Continuous")
    penalty_var.setInitialValue(0.5)

    # テスト用のコンテキスト
    ctx = Context(
        hospitals=[],
        workers=[],
        days=[],
        specified_days={},
        preferences=[],
        max_assignments={},
        required_hd=set(),
        variables={},
        penalties=[(penalty_var, 10.0, {"type": "test"}, "one_person_per_hospital")],
    )

    # ペナルティ行を取得
    rows = list(_iter_penalty_rows(ctx))

    # 結果の検証
    assert len(rows) == 1
    row = rows[0]

    assert row["source"] == "one_person_per_hospital"
    assert row["summary"] == "必要な(病院, 日)ごとに勤務者は1人"
    assert row["var_name"] == "test_penalty"
    assert row["weight"] == 10.0
    assert row["meta"] == {"type": "test"}
