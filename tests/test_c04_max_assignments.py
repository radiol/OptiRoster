import datetime as dt
import importlib
import sys

import pulp
import pytest

from src.domain.types import ShiftType


def _reset_registry_and_module():
    import src.constraints.base as base

    base.constraint_registry.clear()
    sys.modules.pop("src.constraints.c04_max_assignments_per_worker_hospital", None)
    importlib.invalidate_caches()


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry_and_module()
    yield
    _reset_registry_and_module()


def test_cap_is_enforced_and_none_is_unbounded():
    import src.constraints.c04_max_assignments_per_worker_hospital  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = [
        c for c in all_constraints() if c.name == "max_assignments_per_worker_hospital"
    ]

    h = "病院A"
    w1, w2 = "診断02", "診断03"
    d1, d2 = dt.date(2025, 10, 1), dt.date(2025, 10, 2)

    # w1: 上限1, w2: 上限なし
    caps = {(w1, h): 1, (w2, h): None}

    x = {}
    # w1 に2つ候補(→合計は1まで)
    x[(h, w1, d1, ShiftType.DAY)] = pulp.LpVariable("x_w1_d1", 0, 1, cat="Binary")
    x[(h, w1, d2, ShiftType.DAY)] = pulp.LpVariable("x_w1_d2", 0, 1, cat="Binary")
    # w2 に2つ候補(→上限なしなら2つともOK)
    x[(h, w2, d1, ShiftType.DAY)] = pulp.LpVariable("x_w2_d1", 0, 1, cat="Binary")
    x[(h, w2, d2, ShiftType.DAY)] = pulp.LpVariable("x_w2_d2", 0, 1, cat="Binary")

    m = pulp.LpProblem("cap", pulp.LpMaximize)
    m += pulp.lpSum(x.values())

    ctx = {"max_assignments": caps}
    constraint.apply(m, x, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # w1 は合計1に抑えられる
    val_w1 = sum(pulp.value(x[k]) for k in x if k[1] == w1)
    assert val_w1 == 1
    # w2 は合計2取れる
    val_w2 = sum(pulp.value(x[k]) for k in x if k[1] == w2)
    assert val_w2 == 2
