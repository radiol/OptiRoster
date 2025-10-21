from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey
from src.domain.types import ShiftType

from .base import register
from .base_impl import ConstraintBase


class NightSpacing(ConstraintBase):
    """
    NIGHT の最小間隔を g 日にする(任意の連続 g 日ウィンドウで ≤1 件)。
    requires: ctx["days"] : List[date] (最適化対象の日付リスト)
    """

    name = "night_spacing"
    summary = "連続する当直の禁止"
    requires: ClassVar[set[str]] = {"days"}

    def __init__(self, window_days: int = 2):
        """
        window_days = 2  -> 連続禁止(最低1日空け)
        window_days = 5  -> 中4日以上空け(1→6が最短)
        3以上にするとInfeasibleになることがあるので注意
        """
        self.window_days = max(2, int(window_days))

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        days: list[date] = ctx["days"]
        # 並びは安全のため明示ソート
        days = sorted(days)

        # worker x day_index → その日の全病院NIGHTの変数リスト
        by_w_idx: defaultdict[str, defaultdict[int, list[pulp.LpVariable]]] = defaultdict(
            lambda: defaultdict(list)
        )
        day_to_idx = {d: i for i, d in enumerate(days)}

        for (_h, w, d, s), var in x.items():
            if s == ShiftType.NIGHT and d in day_to_idx:
                by_w_idx[w][day_to_idx[d]].append(var)

        # 各 worker について、連続 g 日のどの窓でも ≤1
        g = self.window_days
        for w, idx_map in by_w_idx.items():
            # 連続 g 日ウィンドウ i..i+g-1
            for i in range(0, len(days) - g + 1):
                vars_in_window = []
                for j in range(i, i + g):
                    vars_in_window.extend(idx_map.get(j, []))
                if vars_in_window:
                    model += (
                        pulp.lpSum(vars_in_window) <= 1,
                        f"night_spacing_{w}_{days[i].strftime('%Y%m%d')}_{
                            days[i + g - 1].strftime('%Y%m%d')
                        }",
                    )


register(NightSpacing())
