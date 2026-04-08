from collections.abc import Mapping
from datetime import date, timedelta
from typing import ClassVar, override

import pulp

from src.calendar.utils import is_holiday_or_weekend
from src.constraints.penalty_utils import add_penalties
from src.domain.context import Context, VarKey

from .base import register
from .base_impl import ConstraintBase


class SoftNoConsecutiveHolidayDuty(ConstraintBase):
    """ソフト制約: 連続する休日に同一workerが勤務した場合にペナルティを課す.

    対象: 全シフト種別(DAY, AM, PM, NIGHT).
    条件: d と d+1 が共に休日(土日祝)で, 同一 worker が両日に勤務を持つ場合.
    """

    name = "soft_no_consecutive_holiday_duty"
    summary = "連続する休日の勤務を避ける"
    requires: ClassVar[set[str]] = {"days"}

    def __init__(self, weight: float = 1.0):
        self.weight = float(weight)

    @override
    def _apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        days: list[date] = ctx["days"]
        if not days:
            return

        days_set = set(days)
        penalty_items = []

        for w in {key[1] for key in x}:
            # worker+日ごとに y 変数をキャッシュ (3連休の中間日で再利用)
            y_cache: dict[date, pulp.LpVariable] = {}

            for d in days:
                next_d = d + timedelta(days=1)
                if next_d not in days_set:
                    continue
                if not is_holiday_or_weekend(d) or not is_holiday_or_weekend(next_d):
                    continue

                today_vars = [var for (_, ww, dd, _s), var in x.items() if ww == w and dd == d]
                next_vars = [var for (_, ww, dd, _s), var in x.items() if ww == w and dd == next_d]
                if not today_vars or not next_vars:
                    continue

                # y_today: d に勤務があるか (OR)
                if d not in y_cache:
                    y_t = pulp.LpVariable(
                        f"y_hol_duty_{w}_{d.strftime('%Y%m%d')}",
                        0,
                        1,
                        cat="Binary",
                    )
                    for v in today_vars:
                        model += y_t >= v
                    model += y_t <= pulp.lpSum(today_vars)
                    y_cache[d] = y_t
                y_t = y_cache[d]

                # y_next: d+1 に勤務があるか (OR)
                if next_d not in y_cache:
                    y_n = pulp.LpVariable(
                        f"y_hol_duty_{w}_{next_d.strftime('%Y%m%d')}",
                        0,
                        1,
                        cat="Binary",
                    )
                    for v in next_vars:
                        model += y_n >= v
                    model += y_n <= pulp.lpSum(next_vars)
                    y_cache[next_d] = y_n
                y_n = y_cache[next_d]

                # z = AND(y_t, y_n)
                z = pulp.LpVariable(
                    f"z_consec_hol_{w}_{d.strftime('%Y%m%d')}",
                    0,
                    1,
                    cat="Binary",
                )
                model += z <= y_t
                model += z <= y_n
                model += z >= y_t + y_n - 1

                penalty_items.append(
                    (
                        z,
                        self.weight,
                        {
                            "worker": w,
                            "date": d.isoformat(),
                            "next_date": next_d.isoformat(),
                        },
                    )
                )

        add_penalties(ctx, self.name, penalty_items)


# デフォルト登録
register(SoftNoConsecutiveHolidayDuty())
