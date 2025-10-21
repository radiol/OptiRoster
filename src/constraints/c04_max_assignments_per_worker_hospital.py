from collections import defaultdict
from collections.abc import Mapping
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey

from .base import register
from .base_impl import ConstraintBase


class MaxAssignmentsPerWorkerHospital(ConstraintBase):
    """
    worker*病院ごとの最大勤務回数(CSVで与える):
        ctx["max_assignments"] : Dict[(worker:str, hospital:str), Optional[int]]
    """

    name = "max_assignments_per_worker_hospital"
    summary = "勤務者*病院ごとの最大勤務回数制限"
    requires: ClassVar[set[str]] = {"max_assignments"}

    @override
    def apply(
        self, model: pulp.LpProblem, x: Mapping[VarKey, pulp.LpVariable], ctx: Context
    ) -> None:
        caps = ctx["max_assignments"]  # {(w,h): Optional[int]}
        # (w,h) → [vars...]
        by_wh = defaultdict(list)
        for (h, w, _d, _s), var in x.items():
            by_wh[(w, h)].append(var)

        for (w, h), vars_wh in by_wh.items():
            cap = caps.get((w, h), None)
            if cap is None:
                continue  # 上限なし
            if cap < 0:
                continue  # 念のため
            # Σ_{d,s} x[h,w,d,s] ≤ cap
            model += pulp.lpSum(vars_wh) <= cap, f"max_{w}_{h}"


register(MaxAssignmentsPerWorkerHospital())
