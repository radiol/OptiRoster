from collections.abc import Mapping
from datetime import date, timedelta
from typing import ClassVar, override

import pulp

from src.constraints.penalty_utils import add_penalties
from src.domain.context import Context, VarKey
from src.domain.types import ShiftType

from .base import register
from .base_impl import ConstraintBase


class SoftNoDutyAfterNight(ConstraintBase):
    """
    ソフト制約:
    - 同じ worker が当直(NIGHT)の翌日に勤務(Day/AM)を担当した場合にペナルティを課す。
    - 勤務先はis_remoteに関わらず対象とする。
    """

    name = "soft_no_duty_after_night"
    summary = "当直翌日の外勤を避ける"
    requires: ClassVar[set[str]] = {"days"}

    def __init__(self, weight: float = 0.5):  # ペナルティのweightは軽め
        self.weight = float(weight)

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        days: list[date] = ctx["days"]

        if not days:
            return

        penalty_items = []

        for w in {key[1] for key in x}:
            for d in days:
                next_d = d + timedelta(days=1)
                if next_d not in ctx["days"]:
                    continue  # 次の日が勤務日でない場合はスキップ
                night_vars = [
                    var
                    for (h, ww, dd, s), var in x.items()
                    if ww == w and dd == d and s == ShiftType.NIGHT
                ]
                duty_vars = [
                    var
                    for (_, ww, dd, s), var in x.items()
                    if ww == w and dd == next_d and s in (ShiftType.DAY, ShiftType.AM)
                ]
                if not night_vars or not duty_vars:
                    continue

                # y_night
                y_n = pulp.LpVariable(
                    f"y_night_before_duty_{w}_{d.strftime('%Y%m%d')}", 0, 1, cat="Binary"
                )
                for v in night_vars:
                    model += y_n >= v
                model += y_n <= pulp.lpSum(night_vars)

                # y_next_day_duty
                y_d = pulp.LpVariable(
                    f"y_duty_after_night_{w}_{next_d.strftime('%Y%m%d')}", 0, 1, cat="Binary"
                )
                for v in duty_vars:
                    model += y_d >= v
                model += y_d <= pulp.lpSum(duty_vars)

                # z = AND(y_n, y_d)
                z = pulp.LpVariable(
                    f"z_conflict_night_next_duty_{w}_{d.strftime('%Y%m%d')}",
                    0,
                    1,
                    cat="Binary",
                )
                model += z <= y_n
                model += z <= y_d
                model += z >= y_n + y_d - 1

                penalty_items.append(
                    (
                        z,
                        self.weight,
                        {"worker": w, "night_date": d.isoformat(), "next_date": next_d.isoformat()},
                    )
                )
        add_penalties(ctx, "soft_no_duty_after_night", penalty_items)


# デフォルト登録
register(SoftNoDutyAfterNight())
