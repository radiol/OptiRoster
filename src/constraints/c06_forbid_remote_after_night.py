from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType

from .base import register
from .base_impl import ConstraintBase


class ForbidRemoteAfterNight(ConstraintBase):
    """
    当直(NIGHT) の翌日に is_remote=True かつ (DAY or AM) の勤務を禁止する。
    requires:
        ctx["days"]      : List[date]
        ctx["hospitals"] : List[Hospital]
    """

    name = "forbid_remote_after_night"
    summary = "当直の翌日に遠隔病院の日勤を禁止"
    requires: ClassVar[set[str]] = {"days", "hospitals"}

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        days: list[date] = sorted(ctx["days"])
        hospitals: list[Hospital] = ctx["hospitals"]

        # リモート病院名
        remote_hospitals = {h.name for h in hospitals if h.is_remote}
        if not remote_hospitals:
            return

        # 対象となる翌日のシフト種別
        next_day_forbidden_shifts = {ShiftType.DAY, ShiftType.AM}

        # 各 (worker, d) の当直 → (worker, d+1) のリモート DAY/AM を禁止
        for i, d in enumerate(days):
            if i + 1 >= len(days):
                continue
            d_next = days[i + 1]

            # d の当直変数を集めて、同一 worker の d+1 リモート DAY/AM を締める
            # x: {(h, w, d, s): var}
            for (h, w, dd, s), v_night in x.items():
                if dd != d or s != ShiftType.NIGHT:
                    continue
                # 翌日のリモート(DAY/AM)候補を収集
                remote_next_vars = [
                    v2
                    for (h2, w2, d2, s2), v2 in x.items()
                    if w2 == w
                    and d2 == d_next
                    and h2 in remote_hospitals
                    and s2 in next_day_forbidden_shifts
                ]
                if remote_next_vars:
                    model += (
                        v_night + pulp.lpSum(remote_next_vars) <= 1,
                        f"forbid_remote_after_night_{h}_{w}_{d.strftime('%Y%m%d')}",
                    )


# 自動登録
register(ForbidRemoteAfterNight())
