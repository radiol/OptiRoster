# tests/test_c07_univ_last_holiday_night_specialist_only.py
import datetime as dt

import pulp

from src.domain.types import Hospital, ShiftType, Worker


def test_university_last_holiday_night_forbids_non_specialist(ensure_constraint):
    c = ensure_constraint(
        "src.constraints.c07_univ_last_holiday_night_specialist",
        "univ_last_holiday_night_specialist_only",
    )

    d_sat = dt.date(2025, 10, 4)
    d_sun = dt.date(2025, 10, 5)
    d_mon = dt.date(2025, 10, 6)

    univ = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])
    local = Hospital(name="一般", is_remote=False, is_university=False, demand_rules=[])

    sp = Worker(name="専門", is_diagnostic_specialist=True, assignments=[])
    gen = Worker(name="一般医", is_diagnostic_specialist=False, assignments=[])

    x = {
        (univ.name, gen.name, d_sun, ShiftType.NIGHT): pulp.LpVariable("xUG", 0, 1, cat="Binary"),
        (univ.name, sp.name, d_sun, ShiftType.NIGHT): pulp.LpVariable("xUS", 0, 1, cat="Binary"),
        (local.name, gen.name, d_sun, ShiftType.NIGHT): pulp.LpVariable("xLG", 0, 1, cat="Binary"),
        (univ.name, gen.name, d_mon, ShiftType.NIGHT): pulp.LpVariable("xUGm", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("c07", pulp.LpMaximize)
    m += pulp.lpSum(x.values())
    ctx = {"days": [d_sat, d_sun, d_mon], "hospitals": [univ, local], "workers": [sp, gen]}

    c.apply(m, x, ctx)
    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    assert pulp.value(x[(univ.name, gen.name, d_sun, ShiftType.NIGHT)]) == 0
    assert pulp.value(x[(univ.name, sp.name, d_sun, ShiftType.NIGHT)]) == 1
    assert pulp.value(x[(local.name, gen.name, d_sun, ShiftType.NIGHT)]) == 1
    assert pulp.value(x[(univ.name, gen.name, d_mon, ShiftType.NIGHT)]) == 1
