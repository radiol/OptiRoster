from collections import defaultdict
from collections.abc import Mapping
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey
from src.domain.types import ShiftType

from .base import register
from .base_impl import ConstraintBase


class NoOverlapSameTimeAcrossHospitals(ConstraintBase):
    """
    同一日・同一ワーカーで、別病院における"時間帯がかぶる勤務"の重複を禁止。
    - 同一シフト: DAY-DAY / AM-AM / PM-PM / NIGHT-NIGHT ≤ 1
    - 追加の重複: DAY-AM, DAY-PM ≤ 1
    (AM-PM は許容)
    """

    name = "no_overlap_same_time_across_hospitals"
    summary = "同一の時間帯で重複する勤務を禁止"
    requires: ClassVar[set[str]] = set()

    @override
    def apply(
        self, model: pulp.LpProblem, x: Mapping[VarKey, pulp.LpVariable], ctx: Context
    ) -> None:
        # (w, d) ごとにまとめる
        by_wd = defaultdict(list)
        for (_h, w, d, s), var in x.items():
            by_wd[(w, d)].append((s, var))

        for (w, d), entries in by_wd.items():
            vars_by_shift = defaultdict(list)
            for s, var in entries:
                vars_by_shift[s].append(var)

            # 1) 同一シフトの重複禁止
            for s, vars_s in vars_by_shift.items():
                if vars_s:
                    model += (
                        pulp.lpSum(vars_s) <= 1,
                        f"no_overlap_same_{s.name}_{w}_{d.strftime('%Y%m%d')}",
                    )

            # 2) DAY-AM
            day_am = vars_by_shift.get(ShiftType.DAY, []) + vars_by_shift.get(ShiftType.AM, [])
            if day_am:
                model += (
                    pulp.lpSum(day_am) <= 1,
                    f"no_overlap_DAY_AM_{w}_{d.strftime('%Y%m%d')}",
                )

            # 3) DAY-PM
            day_pm = vars_by_shift.get(ShiftType.DAY, []) + vars_by_shift.get(ShiftType.PM, [])
            if day_pm:
                model += (
                    pulp.lpSum(day_pm) <= 1,
                    f"no_overlap_DAY_PM_{w}_{d.strftime('%Y%m%d')}",
                )


register(NoOverlapSameTimeAcrossHospitals())
