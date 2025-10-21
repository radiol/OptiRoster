import datetime as dt
import importlib
import sys

import pulp
import pytest

import src.constraints.base as base
from src.constraints.base import all_constraints
from src.domain.types import Hospital, ShiftType


def _reset_registry_and_module():
    base.constraint_registry.clear()
    sys.modules.pop("src.constraints.c06_forbid_remote_after_night", None)
    importlib.invalidate_caches()


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry_and_module()
    yield
    _reset_registry_and_module()


def _get_constraint():
    cands = [c for c in all_constraints() if c.name == "forbid_remote_after_night"]
    assert cands, "forbid_remote_after_night not registered"
    return cands[0]


def test_blocks_remote_day_after_night():
    import src.constraints.c06_forbid_remote_after_night  # noqa: F401

    c = _get_constraint()

    h_local = Hospital(name="Local", is_remote=False, is_university=False, demand_rules=[])
    h_remote = Hospital(name="Remote", is_remote=True, is_university=False, demand_rules=[])

    w = "診断01"
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)

    x = {
        (h_local.name, w, d1, ShiftType.NIGHT): pulp.LpVariable("x_night", 0, 1, cat="Binary"),
        (h_remote.name, w, d2, ShiftType.DAY): pulp.LpVariable("x_r_day", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("c06_day", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    ctx = {"days": [d1, d2], "hospitals": [h_local, h_remote]}

    c.apply(m, x, ctx)
    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    v_n = pulp.value(x[(h_local.name, w, d1, ShiftType.NIGHT)])
    v_d = pulp.value(x[(h_remote.name, w, d2, ShiftType.DAY)])
    assert v_n + v_d <= 1  # 同時不可


def test_blocks_remote_am_after_night():
    import src.constraints.c06_forbid_remote_after_night  # noqa: F401

    c = _get_constraint()

    h_local = Hospital(name="Local", is_remote=False, is_university=False, demand_rules=[])
    h_remote = Hospital(name="Remote", is_remote=True, is_university=False, demand_rules=[])

    w = "診断02"
    d1 = dt.date(2025, 10, 5)
    d2 = dt.date(2025, 10, 6)

    x = {
        (h_local.name, w, d1, ShiftType.NIGHT): pulp.LpVariable("x_night2", 0, 1, cat="Binary"),
        (h_remote.name, w, d2, ShiftType.AM): pulp.LpVariable("x_r_am", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("c07_am", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    ctx = {"days": [d1, d2], "hospitals": [h_local, h_remote]}

    c.apply(m, x, ctx)
    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    v_n = pulp.value(x[(h_local.name, w, d1, ShiftType.NIGHT)])
    v_a = pulp.value(x[(h_remote.name, w, d2, ShiftType.AM)])
    assert v_n + v_a <= 1  # 同時不可


def test_allows_remote_pm_or_night_after_night():
    """翌日が Remote x PM or Remote x NIGHT は禁止対象外 → 同時許容。"""
    import src.constraints.c06_forbid_remote_after_night  # noqa: F401

    c = _get_constraint()

    h_local = Hospital(name="Local", is_remote=False, is_university=False, demand_rules=[])
    h_remote = Hospital(name="Remote", is_remote=True, is_university=False, demand_rules=[])

    w = "診断03"
    d1 = dt.date(2025, 10, 10)
    d2 = dt.date(2025, 10, 11)

    x = {
        (h_local.name, w, d1, ShiftType.NIGHT): pulp.LpVariable("x_night3", 0, 1, cat="Binary"),
        (h_remote.name, w, d2, ShiftType.PM): pulp.LpVariable("x_r_pm", 0, 1, cat="Binary"),
        (h_remote.name, w, d2, ShiftType.NIGHT): pulp.LpVariable("x_r_ngt", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("c07_pm_ok", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    ctx = {"days": [d1, d2], "hospitals": [h_local, h_remote]}

    c.apply(m, x, ctx)
    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # PM と NIGHT は禁止対象外 → night翌日の同時も可
    assert pulp.value(x[(h_local.name, w, d1, ShiftType.NIGHT)]) == 1
    assert pulp.value(x[(h_remote.name, w, d2, ShiftType.PM)]) == 1
    assert pulp.value(x[(h_remote.name, w, d2, ShiftType.NIGHT)]) == 1


def test_multiple_remote_hospitals_sum_blocked():
    """翌日が複数のリモート病院(DAY/AM)のときも合計で締める。"""
    import src.constraints.c06_forbid_remote_after_night  # noqa: F401

    c = _get_constraint()

    h_local = Hospital(name="Local", is_remote=False, is_university=False, demand_rules=[])
    h_remote1 = Hospital(name="Remote1", is_remote=True, is_university=False, demand_rules=[])
    h_remote2 = Hospital(name="Remote2", is_remote=True, is_university=False, demand_rules=[])

    w = "診断04"
    d1 = dt.date(2025, 10, 15)
    d2 = dt.date(2025, 10, 16)

    x = {
        (h_local.name, w, d1, ShiftType.NIGHT): pulp.LpVariable("xN", 0, 1, cat="Binary"),
        (h_remote1.name, w, d2, ShiftType.DAY): pulp.LpVariable("xR1", 0, 1, cat="Binary"),
        (h_remote2.name, w, d2, ShiftType.AM): pulp.LpVariable("xR2", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("c07_multi", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    ctx = {"days": [d1, d2], "hospitals": [h_local, h_remote1, h_remote2]}

    c.apply(m, x, ctx)
    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    vN = pulp.value(x[(h_local.name, w, d1, ShiftType.NIGHT)])
    v1 = pulp.value(x[(h_remote1.name, w, d2, ShiftType.DAY)])
    v2 = pulp.value(x[(h_remote2.name, w, d2, ShiftType.AM)])
    # 翌日の Remote(DAY/AM) は“合計”で締められる
    assert vN + v1 + v2 <= 2  # night + (remote day or am) の同時は不可
