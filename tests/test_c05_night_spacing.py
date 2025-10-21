import datetime as dt
import importlib
import sys

import pulp
import pytest

from src.domain.types import ShiftType


def _reset_registry_and_module():
    import src.constraints.base as base

    base.constraint_registry.clear()
    sys.modules.pop("src.constraints.c05_night_spacing", None)
    importlib.invalidate_caches()


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry_and_module()
    yield
    _reset_registry_and_module()


def test_no_two_nights_within_5day_window():
    # 読み込みで register(window_days=5) が走る前提
    import src.constraints.c05_night_spacing  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = [c for c in all_constraints() if c.name == "night_spacing"]

    w = "診断01"
    h1 = "A病院"
    h2 = "B病院"
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)  # 連続当直不可
    d3 = dt.date(2025, 10, 3)  # 中1日以上空ければOK

    x = {
        (h1, w, d1, ShiftType.NIGHT): pulp.LpVariable("x1", 0, 1, cat="Binary"),
        (h2, w, d2, ShiftType.NIGHT): pulp.LpVariable("x2", 0, 1, cat="Binary"),
        (h1, w, d3, ShiftType.NIGHT): pulp.LpVariable("x3", 0, 1, cat="Binary"),
    }
    m = pulp.LpProblem("spacing", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    ctx = {"days": [d1, d2, d3]}
    constraint.apply(m, x, ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    v = {k: pulp.value(vv) for k, vv in x.items()}
    # d1 と d2 は同時不可(どちらか1つまで)
    assert v[(h1, w, d1, ShiftType.NIGHT)] + v[(h2, w, d2, ShiftType.NIGHT)] <= 1
    # d1 と d3 は同時可(合計2もあり得る)
    assert v[(h1, w, d1, ShiftType.NIGHT)] + v[(h1, w, d3, ShiftType.NIGHT)] in (1, 2)
