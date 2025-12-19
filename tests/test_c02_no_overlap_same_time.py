# tests/test_c02_no_overlap_same_time.py
import datetime as dt
import importlib
import sys

import pulp
import pytest

from src.domain.types import ShiftType


def _reset_registry_and_module():
    import src.constraints.base as base

    base.constraint_registry.clear()
    sys.modules.pop("src.constraints.c02_no_overlap_same_time", None)
    importlib.invalidate_caches()


@pytest.fixture(autouse=True)
def _clean():
    _reset_registry_and_module()
    yield
    _reset_registry_and_module()


def test_plugin_registers_on_import():
    from src.constraints.base import all_constraints

    assert all_constraints() == []
    import src.constraints.c02_no_overlap_same_time  # noqa: F401

    names = [c.name for c in all_constraints()]
    assert "no_overlap_same_time_across_hospitals" in names


def test_same_shift_across_hospitals_forbidden():
    """
    同一日・同一ワーカー・別病院で DAY-DAY は不可 → 片方のみ選ばれる
    """
    import src.constraints.c02_no_overlap_same_time  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h1, h2 = "A病院", "B病院"
    w = "山田"
    d = dt.date(2025, 9, 1)

    x = {}
    x[(h1, w, d, ShiftType.DAY)] = pulp.LpVariable("x_A_DAY", 0, 1, cat="Binary")
    x[(h2, w, d, ShiftType.DAY)] = pulp.LpVariable("x_B_DAY", 0, 1, cat="Binary")

    model = pulp.LpProblem("same_shift", pulp.LpMaximize)
    model += pulp.lpSum(x.values())

    constraint.apply(model, x, ctx={})
    status = model.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    chosen = [k for k, v in x.items() if pulp.value(v) == 1]
    assert len(chosen) == 1  # 片方のみ


def test_day_with_am_forbidden_but_am_pm_allowed():
    """
    同一日・同一ワーカー:
      - DAY-AM は不可 → 合計1つだけ
      - AM-PM は許容 → 合計2つ選べる
    """
    import src.constraints.c02_no_overlap_same_time  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h1, h2 = "A病院", "B病院"
    w = "佐藤"
    d = dt.date(2025, 9, 2)

    # ケース1: DAY-AM 禁止
    x1 = {
        (h1, w, d, ShiftType.DAY): pulp.LpVariable("x1_DAY", 0, 1, cat="Binary"),
        (h2, w, d, ShiftType.AM): pulp.LpVariable("x1_AM", 0, 1, cat="Binary"),
    }
    m1 = pulp.LpProblem("day_am", pulp.LpMaximize)
    m1 += pulp.lpSum(x1.values())
    constraint.apply(m1, x1, ctx={})
    s1 = m1.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[s1] == "Optimal"
    assert sum(pulp.value(v) for v in x1.values()) == 1  # 片方のみ

    # ケース2: AM-PM 許容
    x2 = {
        (h1, w, d, ShiftType.AM): pulp.LpVariable("x2_AM", 0, 1, cat="Binary"),
        (h2, w, d, ShiftType.PM): pulp.LpVariable("x2_PM", 0, 1, cat="Binary"),
    }
    m2 = pulp.LpProblem("am_pm", pulp.LpMaximize)
    m2 += pulp.lpSum(x2.values())
    constraint.apply(m2, x2, ctx={})
    s2 = m2.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[s2] == "Optimal"
    assert sum(pulp.value(v) for v in x2.values()) == 2  # 両方選べる


def test_night_overlap_forbidden_across_hospitals():
    """
    同一日・同一ワーカー・別病院で NIGHT-NIGHT は不可 → 合計1つだけ
    """
    import src.constraints.c02_no_overlap_same_time  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h1, h2 = "A病院", "B病院"
    w = "高橋"
    d = dt.date(2025, 9, 3)

    x = {
        (h1, w, d, ShiftType.NIGHT): pulp.LpVariable("xN1", 0, 1, cat="Binary"),
        (h2, w, d, ShiftType.NIGHT): pulp.LpVariable("xN2", 0, 1, cat="Binary"),
    }
    m = pulp.LpProblem("night_night", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    constraint.apply(m, x, ctx={})
    s = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[s] == "Optimal"
    assert sum(pulp.value(v) for v in x.values()) == 1


def test_night_with_day_allowed_on_weekday():
    """
    平日: NIGHT は DAY と同一日に可能(現状仕様)
    -> 合計2つ選べる
    """
    import src.constraints.c02_no_overlap_same_time  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h1, h2 = "A病院", "B病院"
    w = "鈴木"
    d = dt.date(2025, 9, 4)  # Thu (weekday)

    x = {
        (h1, w, d, ShiftType.NIGHT): pulp.LpVariable("x_weekday_NIGHT", 0, 1, cat="Binary"),
        (h2, w, d, ShiftType.DAY): pulp.LpVariable("x_weekday_DAY", 0, 1, cat="Binary"),
    }
    m = pulp.LpProblem("weekday_night_day", pulp.LpMaximize)
    m += pulp.lpSum(x.values())

    constraint.apply(m, x, ctx={})
    s = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[s] == "Optimal"
    assert sum(pulp.value(v) for v in x.values()) == 2  # both can be chosen


def test_night_with_day_forbidden_on_holiday_or_weekend():
    """
    休日(土日祝+年末年始): NIGHT は1日勤務扱い
    -> NIGHT と DAY は同一日に不可 -> 合計1つだけ
    """
    import src.constraints.c02_no_overlap_same_time  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h1, h2 = "A病院", "B病院"
    w = "伊藤"
    d = dt.date(2025, 12, 29)  # Mon, but year-end/new-year rule => holiday_or_weekend == True

    x = {
        (h1, w, d, ShiftType.NIGHT): pulp.LpVariable("x_holi_NIGHT", 0, 1, cat="Binary"),
        (h2, w, d, ShiftType.DAY): pulp.LpVariable("x_holi_DAY", 0, 1, cat="Binary"),
    }
    m = pulp.LpProblem("holiday_night_day", pulp.LpMaximize)
    m += pulp.lpSum(x.values())

    constraint.apply(m, x, ctx={})
    s = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[s] == "Optimal"
    assert sum(pulp.value(v) for v in x.values()) == 1  # only one can be chosen


def test_am_pm_still_allowed_on_holiday_or_weekend():
    """
    休日でも AM-PM は許容(現状仕様維持)
    -> 合計2つ選べる
    """
    import src.constraints.c02_no_overlap_same_time  # noqa: F401
    from src.constraints.base import all_constraints

    (constraint,) = all_constraints()

    h1, h2 = "A病院", "B病院"
    w = "田中"
    d = dt.date(2025, 12, 29)  # holiday_or_weekend == True

    x = {
        (h1, w, d, ShiftType.AM): pulp.LpVariable("x_holi_AM", 0, 1, cat="Binary"),
        (h2, w, d, ShiftType.PM): pulp.LpVariable("x_holi_PM", 0, 1, cat="Binary"),
    }
    m = pulp.LpProblem("holiday_am_pm", pulp.LpMaximize)
    m += pulp.lpSum(x.values())

    constraint.apply(m, x, ctx={})
    s = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[s] == "Optimal"
    assert sum(pulp.value(v) for v in x.values()) == 2  # both can be chosen
