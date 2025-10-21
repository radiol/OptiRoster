import datetime as dt

import pulp

from src.domain.types import Hospital, ShiftType
from src.optimizer.objective import set_objective_with_penalties


def test_penalty_applied_when_same_day_night_and_remote_daypm(ensure_constraint):
    c = ensure_constraint(
        "src.constraints.s02_soft_no_night_remote_daypm_same_day",
        "soft_no_night_remote_daypm_same_day",
    )

    h_local = Hospital("Local", is_remote=False, is_university=False, demand_rules=[])
    h_remote = Hospital("Remote", is_remote=True, is_university=False, demand_rules=[])

    w = "診断01"
    d = dt.date(2025, 10, 1)

    x = {
        (h_local.name, w, d, ShiftType.NIGHT): pulp.LpVariable("xN", 0, 1, cat="Binary"),
        (h_remote.name, w, d, ShiftType.DAY): pulp.LpVariable("xR", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("soft_same_day", pulp.LpMaximize)
    ctx = {"days": [d], "hospitals": [h_local, h_remote]}

    # 制約適用
    c.apply(m, x, ctx)

    # 目的設定(合計 - ペナルティ)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.PULP_CBC_CMD(msg=False))
    assert pulp.LpStatus[status] == "Optimal"

    # Night+RemoteDayの両立はペナルティで避けられる → 典型解では片方が立つ
    vN = pulp.value(x[(h_local.name, w, d, ShiftType.NIGHT)])
    vR = pulp.value(x[(h_remote.name, w, d, ShiftType.DAY)])
    assert vN + vR <= 1


def test_no_penalty_if_only_night_or_only_remote(ensure_constraint):
    c = ensure_constraint(
        "src.constraints.s02_soft_no_night_remote_daypm_same_day",
        "soft_no_night_remote_daypm_same_day",
    )

    h_remote = Hospital("Remote", is_remote=True, is_university=False, demand_rules=[])
    w = "診断02"
    d = dt.date(2025, 10, 2)

    x = {
        (h_remote.name, w, d, ShiftType.DAY): pulp.LpVariable("xR", 0, 1, cat="Binary"),
    }

    m = pulp.LpProblem("soft_ok", pulp.LpMaximize)
    ctx = {"days": [d], "hospitals": [h_remote]}
    c.apply(m, x, ctx)

    # ペナルティが積まれないこと
    assert not ctx.get("penalties")
