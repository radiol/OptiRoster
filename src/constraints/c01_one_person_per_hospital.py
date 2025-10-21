from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey

from .base import register
from .base_impl import ConstraintBase


class OnePersonPerHospital(ConstraintBase):
    name = "one_person_per_hospital"
    summary = "必要な(病院, 日)ごとに勤務者は1人"
    requires: ClassVar[set[str]] = {"required_hd"}

    @override
    def apply(
        self, model: pulp.LpProblem, x: Mapping[VarKey, pulp.LpVariable], ctx: Context
    ) -> None:
        self.ensure_requires(ctx)
        # 各病院が必要な (病院, 日) ごとに、1人だけ割り当てる。
        required_hd = ctx["required_hd"]  # set((h,d), ...)
        by_hd = defaultdict(list)
        for (h, _, d, _), var in x.items():
            by_hd[(h, d)].append(var)

        slack_map: dict[tuple[str, date], pulp.LpVariable] = ctx.setdefault("shortage_slack", {})

        for h, d in required_hd:
            vars_hd = by_hd.get((h, d), [])
            s = pulp.LpVariable(f"s_short_{h}_{d.strftime('%Y%m%d')}", lowBound=0, cat="Binary")
            slack_map[(h, d)] = s
            model += pulp.lpSum(vars_hd) + s == 1, f"one_person_{h}_{d.strftime('%Y%m%d')}"


register(OnePersonPerHospital())
