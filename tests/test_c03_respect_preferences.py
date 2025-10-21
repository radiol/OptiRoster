# tests/test_c03_respect_preferences.py
import datetime as dt
import importlib
import sys

import pulp
import pytest

from src.domain.types import ShiftType
from src.io.preferences_loader import PreferenceStatus


def _reset_registry_and_module():
    import src.constraints.base as base

    base.constraint_registry.clear()
    sys.modules.pop("src.constraints.c03_respect_preferences", None)
    importlib.invalidate_caches()


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry_and_module()
    yield
    _reset_registry_and_module()


def test_plugin_registers_on_import():
    from src.constraints.base import all_constraints

    assert all_constraints() == []
    import src.constraints.c03_respect_preferences  # noqa: F401

    names = [c.name for c in all_constraints()]
    assert "respect_preferences_from_csv" in names


def test_forbid_night_and_all_shifts():
    import src.constraints.c03_respect_preferences  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = [c for c in all_constraints() if c.name == "respect_preferences_from_csv"]

    h = "A病院"
    w1 = "田中"
    w2 = "佐藤"
    d = dt.date(2025, 9, 1)

    # 田中: 当直不可 → NIGHT=0, DAYは可
    # 佐藤: 日勤・当直不可 → 全シフト0
    x = {
        (h, w1, d, ShiftType.DAY): pulp.LpVariable("x_tanaka_day", 0, 1, cat="Binary"),
        (h, w1, d, ShiftType.NIGHT): pulp.LpVariable("x_tanaka_night", 0, 1, cat="Binary"),
        (h, w2, d, ShiftType.DAY): pulp.LpVariable("x_sato_day", 0, 1, cat="Binary"),
        (h, w2, d, ShiftType.NIGHT): pulp.LpVariable("x_sato_night", 0, 1, cat="Binary"),
        (h, w2, d, ShiftType.AM): pulp.LpVariable("x_sato_am", 0, 1, cat="Binary"),
    }

    ctx = {
        "preferences": {
            (w1, d): PreferenceStatus.NIGHT_FORBIDDEN,
            (w2, d): PreferenceStatus.DAY_NIGHT_FORBIDDEN,
        }
    }

    m = pulp.LpProblem("pref", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    constraint.apply(m, x, ctx)

    # 解くと、禁止された変数は 0 に固定
    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    assert pulp.value(x[(h, w1, d, ShiftType.NIGHT)]) == 0
    assert pulp.value(x[(h, w2, d, ShiftType.DAY)]) == 0
    assert pulp.value(x[(h, w2, d, ShiftType.NIGHT)]) == 0
    assert pulp.value(x[(h, w2, d, ShiftType.AM)]) == 0
