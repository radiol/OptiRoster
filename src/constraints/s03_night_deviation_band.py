from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.calendar.utils import is_holiday_or_weekend
from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType

from .base import register
from .base_impl import ConstraintBase
from .penalty_utils import add_penalties


class SoftNightDeviationBand(ConstraintBase):
    """
    病院ごとに、Night の“重み付き”回数を平均±1のバンドに収めるよう誘導するソフト制約。
        - 重み: 平日=1.0, 休日(=土日祝)=2.0
        - A_h = T_h / K_h (T_h: その病院の月間 Night 総重み、K_h: Nightに入れる候補者数)
        - 各 worker の c_{h,w}(重み付き回数)に対して:
            over >= c_{h,w} - ceil(A_h)
            under >= floor(A_h) - c_{h,w}
        を置き、平均から超える(over)か下回る(under)でそれぞれペナルティを追加

    requires: {"hospitals"}  # days/workers は x から復元する
    """

    name = "soft_night_deviation_band"
    summary = "病院ごとの当直回数の偏りを避ける"
    requires: ClassVar[set[str]] = {"hospitals"}

    def __init__(
        self,
        weight_over: float = 3.0,
        weight_under: float = 3.0,
        min_candidate_nights: int = 2,  # 候補日が極端に少ない人(候補日が2日未満)は対象外に
        holiday_weight: float = 2.0,  # 平日=1.0, 休日=2.0
    ):
        self.weight_over = float(weight_over)
        self.weight_under = float(weight_under)
        self.min_cand = int(min_candidate_nights)
        self.holi_w = float(holiday_weight)

    def _wd(self, d: date) -> float:
        return self.holi_w if is_holiday_or_weekend(d) else 1.0

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        hospitals: list[Hospital] = ctx["hospitals"]

        # (h,w) -> [(d,var)]  (Night のみ)
        hw_vars: dict[tuple[str, str], list[tuple[date, pulp.LpVariable]]] = {}
        # 病院ごとの Night 対象日(候補変数が存在する日)を集計
        night_days_by_h: dict[str, set[date]] = {}

        for (h, w, d, s), var in x.items():
            if s == ShiftType.NIGHT:
                hw_vars.setdefault((h, w), []).append((d, var))
                night_days_by_h.setdefault(h, set()).add(d)

        penalty_items = []

        for h in (hh.name for hh in hospitals):
            # その病院で Night に入れる候補者(候補日が min_cand 以上)
            Wh = [w for (hh, w) in hw_vars if hh == h and len(hw_vars[(h, w)]) >= self.min_cand]
            Kh = len(Wh)
            days_h = sorted(night_days_by_h.get(h, []))
            if Kh <= 1 or not days_h:
                continue

            # 総需要(重み付き) T_h と平均 A_h
            Th = sum(self._wd(d) for d in days_h)
            Ah = Th / Kh
            Lh = int(Ah)  # floor
            Uh = Lh + 1  # ceil

            # 各人の重み付きカウント
            counts = {}
            for w in Wh:
                terms = [self._wd(d) * var for (d, var) in hw_vars[(h, w)]]
                counts[w] = pulp.lpSum(terms) if terms else pulp.lpSum([])

            # バンド外だけペナルティ
            for w in Wh:
                over = pulp.LpVariable(f"night_dev_over_{h}_{w}", lowBound=0)
                under = pulp.LpVariable(f"night_dev_under_{h}_{w}", lowBound=0)
                model += over >= counts[w] - Uh
                model += under >= Lh - counts[w]

                penalty_items.append(
                    (over, self.weight_over, {"hospital": h, "worker": w, "kind": "over"})
                )
                penalty_items.append(
                    (under, self.weight_under, {"hospital": h, "worker": w, "kind": "under"})
                )

        add_penalties(ctx, self.name, penalty_items)


register(SoftNightDeviationBand())
