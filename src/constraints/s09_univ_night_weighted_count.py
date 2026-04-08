from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, override

import pulp

from src.calendar.utils import is_holiday_or_weekend
from src.constraints.penalty_utils import add_penalties
from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType

from .base import register
from .base_impl import ConstraintBase


class SoftUnivNightWeightedCount(ConstraintBase):
    """
    大学病院(is_university=True)の当直(NIGHT)について,
    各workerの1ヶ月の重み付き合計回数がlimitを超えた場合に線形ペナルティを課す.
    - 休日(is_holiday_or_weekend=True): holiday_weight カウント(default=2)
    - 平日: weekday_weight カウント(default=1)
    - 超過量 1 単位あたり weight のペナルティ(default=5.0)
    """

    name = "soft_univ_night_weighted_count"
    summary = "大学病院の当直回数を月3コマ以下に制限(当直1コマ, 日当直2コマ)"
    requires: ClassVar[set[str]] = {"hospitals"}

    def __init__(
        self,
        limit: int = 3,
        holiday_weight: int = 2,
        weekday_weight: int = 1,
        weight: float = 10.0,
    ):
        self.limit = int(limit)
        self.holiday_weight = int(holiday_weight)
        self.weekday_weight = int(weekday_weight)
        self.weight = float(weight)

    @override
    def _apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        hospitals: list[Hospital] = ctx["hospitals"]
        univ_names = {h.name for h in hospitals if h.is_university}
        if not univ_names:
            return

        # worker ごとに大学病院 NIGHT 変数を収集
        # {worker: [(day_weight, var), ...]}
        worker_vars: dict[str, list[tuple[int, pulp.LpVariable]]] = {}
        for (h, w, d, s), var in x.items():
            if h not in univ_names or s != ShiftType.NIGHT:
                continue
            day_weight = self.holiday_weight if is_holiday_or_weekend(d) else self.weekday_weight
            worker_vars.setdefault(w, []).append((day_weight, var))

        penalty_items = []
        for w, wv_list in worker_vars.items():
            weighted_sum = pulp.lpSum(dw * v for dw, v in wv_list)
            over = pulp.LpVariable(f"univ_night_wcount_over_{w}", lowBound=0)
            model += over >= weighted_sum - self.limit
            penalty_items.append((over, self.weight, {"worker": w}))

        add_penalties(ctx, self.name, penalty_items)


register(SoftUnivNightWeightedCount())
