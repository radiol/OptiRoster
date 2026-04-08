from collections.abc import Mapping
from datetime import date, timedelta
from typing import ClassVar, override

import pulp

from src.constraints.penalty_utils import add_penalties
from src.domain.context import Context, VarKey
from src.domain.types import Hospital

from .base import register
from .base_impl import ConstraintBase


class SoftNoConsecutiveRemote(ConstraintBase):
    """ソフト制約: is_remote=True の病院への勤務が2日連続した場合にペナルティを課す.

    対象: 全シフト種別(DAY, AM, PM, NIGHT).
    条件: d と d+1 の両日に同一 worker が remote 病院で勤務を持つ場合.
    """

    name = "soft_no_consecutive_remote"
    summary = "遠隔地の連続勤務を避ける"
    requires: ClassVar[set[str]] = {"days", "hospitals"}

    def __init__(self, weight: float = 0.5):  # ペナルティのweightは軽め
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

        hospitals: list[Hospital] = ctx["hospitals"]
        remote_hospitals = {h.name for h in hospitals if h.is_remote}
        if not remote_hospitals:
            return

        days_set = set(days)
        penalty_items = []

        for w in {key[1] for key in x}:
            # worker+日ごとに y 変数をキャッシュ (3連続の中間日で再利用)
            y_cache: dict[date, pulp.LpVariable] = {}

            for d in days:
                next_d = d + timedelta(days=1)
                if next_d not in days_set:
                    continue

                # d のremote勤務変数
                today_vars = [
                    var
                    for (h, ww, dd, _s), var in x.items()
                    if ww == w and dd == d and h in remote_hospitals
                ]
                # d+1 のremote勤務変数
                next_vars = [
                    var
                    for (h, ww, dd, _s), var in x.items()
                    if ww == w and dd == next_d and h in remote_hospitals
                ]
                if not today_vars or not next_vars:
                    continue

                # y_today: d にremote勤務があるか (OR)
                if d not in y_cache:
                    y_t = pulp.LpVariable(
                        f"y_remote_{w}_{d.strftime('%Y%m%d')}",
                        0,
                        1,
                        cat="Binary",
                    )
                    for v in today_vars:
                        model += y_t >= v
                    model += y_t <= pulp.lpSum(today_vars)
                    y_cache[d] = y_t
                y_t = y_cache[d]

                # y_next: d+1 にremote勤務があるか (OR)
                if next_d not in y_cache:
                    y_n = pulp.LpVariable(
                        f"y_remote_{w}_{next_d.strftime('%Y%m%d')}",
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
                    f"z_consec_remote_{w}_{d.strftime('%Y%m%d')}",
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
register(SoftNoConsecutiveRemote())
