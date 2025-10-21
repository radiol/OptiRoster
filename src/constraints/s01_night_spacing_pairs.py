from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.constraints.penalty_utils import add_penalties
from src.domain.context import Context, VarKey
from src.domain.types import ShiftType

from .base import register
from .base_impl import ConstraintBase


class SoftNightSpacingPairs(ConstraintBase):
    """
    NIGHT の“近接”をできるだけ避けるためのソフト制約。
    - 同一 worker の 2 つの当直日 (d1,d2) の距離 Δ が 1〜5 ならペナルティを課す
        (Δ が小さいほど重い)。Δ >= 6 はペナルティなし。
    - 線形化のため、y[w,d](そのワーカーが d に当直か)と z[w,d1,d2](そのペアが同時に選ばれたか)
        の補助二値を導入。
    - 既存の c05_night_spacing(window=2) と併用推奨(連続禁止はハードで保証)。
    requires:
        ctx["days"]: List[date]
    """

    name = "soft_night_spacing_pairs"
    summary = "当直間隔を可能な限り空ける"
    requires: ClassVar[set[str]] = {"days"}

    def __init__(self, max_no_penalty_gap: int = 6, base_weight: float = 3.0):
        """
        max_no_penalty_gap: これ以上離れていればペナルティなし(デフォルト: 6 日以上)
        base_weight: 重みのスケール(Δ=1 のとき 5*base_weight、Δ=5 のとき 1*base_weight)
        """
        self.no_penalty_gap = int(max_no_penalty_gap)
        self.base_weight = float(base_weight)

    def _weight(self, delta_days: int) -> float:
        # Δ in [1..5] → 5,4,3,2,1 の重み(* base_weight)
        return max(0, self.no_penalty_gap - delta_days) * self.base_weight

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        days: list[date] = sorted(ctx["days"])
        if not days:
            return

        # worker x day → その日に割当可能な「全病院の NIGHT 変数」集合
        by_w_d: dict[str, dict[date, list[pulp.LpVariable]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for (_h, w, d, s), var in x.items():
            if s == ShiftType.NIGHT:
                by_w_d[w][d].append(var)

        penalty_items = []

        # y[w,d]: そのワーカーが d に当直するか(1 if any NIGHT chosen that day)
        y_vars: dict[tuple[str, date], pulp.LpVariable] = {}
        for w, m in by_w_d.items():
            for d, vars_on_d in m.items():
                y = pulp.LpVariable(
                    f"night_ind_{w}_{d.strftime('%Y%m%d')}",
                    lowBound=0,
                    upBound=1,
                    cat="Binary",
                )
                # y ≥ 各変数、y ≤ その日の合計
                for v in vars_on_d:
                    model += y >= v
                model += y <= pulp.lpSum(vars_on_d)
                y_vars[(w, d)] = y

        # ペア z[w,d1,d2] を作って距離別にペナルティ
        for w, m in by_w_d.items():
            dlist = sorted(m.keys())
            for i in range(len(dlist)):
                for j in range(i + 1, len(dlist)):
                    d1, d2 = dlist[i], dlist[j]
                    delta = (d2 - d1).days
                    weight = self._weight(delta)
                    if weight <= 0:
                        continue

                    y1 = y_vars[(w, d1)]
                    y2 = y_vars[(w, d2)]
                    # z = AND(y1, y2) を線形化
                    z = pulp.LpVariable(
                        f"soft_night_spacing_{w}_{d1.strftime('%Y%m%d')}_{d2.strftime('%Y%m%d')}",
                        lowBound=0,
                        upBound=1,
                        cat="Binary",
                    )
                    model += z <= y1
                    model += z <= y2
                    model += z >= y1 + y2 - 1

                    penalty_items.append(
                        (z, weight, {"worker": w, "d1": d1, "d2": d2, "delta": delta})
                    )

        # ctx にペナルティ和を登録
        # main.pyではsrc/optimizer/objective.pyのset_objective_with_penaltiesで目的関数に組み込む
        add_penalties(ctx, self.name, penalty_items)


# デフォルト:6日以上はペナルティなし、Δ=1..5 に 5..1 のペナルティ
register(SoftNightSpacingPairs())
