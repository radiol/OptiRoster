from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.constraints.penalty_utils import add_penalties
from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType

from .base import register
from .base_impl import ConstraintBase


class SoftNoNightRemoteDayPmSameDay(ConstraintBase):
    """
    ソフト制約:
    - 同じ worker が同一日に
        (NIGHT) と (is_remote=True の DAY or PM)を両方担当した場合にペナルティを課す。
    """

    name = "soft_no_night_remote_daypm_same_day"
    summary = "同一日に当直と遠隔病院の日勤・PM勤務の重複を避ける"
    requires: ClassVar[set[str]] = {"days", "hospitals"}

    def __init__(self, weight: float = 1.0):  # ペナルティのweightは軽め
        self.weight = float(weight)

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        days: list[date] = ctx["days"]
        hospitals: list[Hospital] = ctx["hospitals"]
        remote_hospitals = {h.name for h in hospitals if h.is_remote}

        if not days or not remote_hospitals:
            return

        penalty_items = []

        for w in {key[1] for key in x}:
            for d in days:
                night_vars = [
                    var
                    for (h, ww, dd, s), var in x.items()
                    if ww == w and dd == d and s == ShiftType.NIGHT
                ]
                remote_daypm_vars = [
                    var
                    for (h, ww, dd, s), var in x.items()
                    if ww == w
                    and dd == d
                    and h in remote_hospitals
                    and s in (ShiftType.DAY, ShiftType.PM)
                ]

                if night_vars and remote_daypm_vars:
                    # y_night
                    y_n = pulp.LpVariable(f"y_night_{w}_{d.strftime('%Y%m%d')}", 0, 1, cat="Binary")
                    for v in night_vars:
                        model += y_n >= v
                    model += y_n <= pulp.lpSum(night_vars)

                    # y_remote_daypm
                    y_r = pulp.LpVariable(
                        f"y_remote_daypm_{w}_{d.strftime('%Y%m%d')}", 0, 1, cat="Binary"
                    )
                    for v in remote_daypm_vars:
                        model += y_r >= v
                    model += y_r <= pulp.lpSum(remote_daypm_vars)

                    # z = AND(y_n, y_r)
                    z = pulp.LpVariable(
                        f"z_conflict_night_remote_{w}_{d.strftime('%Y%m%d')}",
                        0,
                        1,
                        cat="Binary",
                    )
                    model += z <= y_n
                    model += z <= y_r
                    model += z >= y_n + y_r - 1

                    penalty_items.append((z, self.weight, {"worker": w, "date": d.isoformat()}))
        add_penalties(ctx, "soft_no_night_remote_daypm_same_day", penalty_items)


# デフォルト登録
register(SoftNoNightRemoteDayPmSameDay())
