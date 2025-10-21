from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, override

import pulp

from src.calendar.utils import is_last_holiday
from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType, Worker

from .base import register
from .base_impl import ConstraintBase


class UnivLastHolidayNightSpecialistOnly(ConstraintBase):
    """
    連休(土日祝の連続)の最終日の【大学病院 x 当直】は
    is_diagnostic_specialist=True の勤務者のみ許可。
    それ以外(非専門)は禁止(var == 0)。
    """

    name = "univ_last_holiday_night_specialist_only"
    summary = "連休最終日の大学病院当直は診断専門医が担当"
    requires: ClassVar[set[str]] = {"days", "hospitals", "workers"}

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        ctx["days"]
        hospitals: list[Hospital] = ctx["hospitals"]
        workers: list[Worker] = ctx["workers"]

        univ_hospitals = {h.name for h in hospitals if h.is_university}
        specialists = {w.name for w in workers if w.is_diagnostic_specialist}

        # 該当条件:大学病院 x NIGHT x 連休最終日 x 非専門 → 禁止
        for (h, w, d, s), var in x.items():
            if (
                h in univ_hospitals
                and s == ShiftType.NIGHT
                and is_last_holiday(d)
                and w not in specialists
            ):
                cname = (
                    f"forbid_univ_last_holiday_night_non_specialist_{h}_{w}_{d.strftime('%Y%m%d')}"
                )
                model += (var == 0, cname)


register(UnivLastHolidayNightSpecialistOnly())
