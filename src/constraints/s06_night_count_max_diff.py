from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType

from .base import register
from .base_impl import ConstraintBase
from .penalty_utils import add_penalties


class SoftNightCountMaxDiff(ConstraintBase):
    """
    病院ごとに, Night の"重み付けなし"回数で,
    最小の人と最大の人の差が1以下になるよう誘導するソフト制約.
    各病院で:
        - 候補者の中で最小回数をmin_count, 最大回数をmax_countとする
        - max_count - min_count <= 1 となるようペナルティを追加

    requires: {"hospitals"}  # days/workers は x から復元する
    """

    name = "soft_night_count_max_diff"
    summary = "病院ごとの当直回数の最大・最小差を1以下に制限"
    requires: ClassVar[set[str]] = {"hospitals"}

    def __init__(
        self,
        weight: float = 5.0,  # 差が1を超えた場合のペナルティ重み
        min_candidate_nights: int = 2,  # 候補日が極端に少ない人(候補日が2日未満)は対象外に
    ):
        self.weight = float(weight)
        self.min_candidate_nights = int(min_candidate_nights)

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

        for (h, w, d, s), var in x.items():
            if s == ShiftType.NIGHT:
                hw_vars.setdefault((h, w), []).append((d, var))

        penalty_items = []

        for h in (hh.name for hh in hospitals):
            # その病院で Night に入れる候補者(候補日が min_candidate_nights 以上)
            Wh = [
                w
                for (hh, w) in hw_vars
                if hh == h and len(hw_vars[(h, w)]) >= self.min_candidate_nights
            ]
            if len(Wh) <= 1:
                continue  # 候補者が1人以下なら対象外

            # 各人の重み付けなし回数
            counts = {}
            for w in Wh:
                terms = [var for (d, var) in hw_vars[(h, w)]]
                counts[w] = pulp.lpSum(terms) if terms else pulp.lpSum([])

            # 最小・最大回数を表す変数
            min_count = pulp.LpVariable(f"night_min_{h}", lowBound=0)
            max_count = pulp.LpVariable(f"night_max_{h}", lowBound=0)

            # 制約: min_count <= counts[w] <= max_count for all w in Wh
            for w in Wh:
                model += min_count <= counts[w], f"night_min_bound_{h}_{w}"
                model += counts[w] <= max_count, f"night_max_bound_{h}_{w}"

            # 差が1を超える部分に対するペナルティ変数
            excess_diff = pulp.LpVariable(f"night_excess_diff_{h}", lowBound=0)

            # excess_diff >= (max_count - min_count) - 1
            model += excess_diff >= max_count - min_count - 1, f"night_diff_penalty_{h}"

            penalty_items.append(
                (excess_diff, self.weight, {"hospital": h, "kind": "max_diff_excess"})
            )

        add_penalties(ctx, self.name, penalty_items)


register(SoftNightCountMaxDiff())
