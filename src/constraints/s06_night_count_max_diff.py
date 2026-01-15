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
    平均値ベースの負荷分散を行うソフト制約.
    各病院で:
        - 対象者(2回以上勤務できる人)の総Night勤務回数を計算
        - 対象者数で割って平均を導出
        - 平均値の前後の整数値以外の勤務回数を持つ対象者にペナルティを設定

    requires: {"hospitals"}  # days/workers は x から復元する
    """

    name = "soft_night_count_max_diff"
    summary = "病院ごとの当直回数(重みなし)の偏りを避ける"
    requires: ClassVar[set[str]] = {"hospitals"}

    def __init__(
        self,
        weight: float = 5.0,  # 平均から外れた場合のペナルティ重み
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
        # 病院ごとの Night 対象日(候補変数が存在する日)を集計
        night_days_by_h: dict[str, set[date]] = {}

        for (h, w, d, s), var in x.items():
            if s == ShiftType.NIGHT:
                hw_vars.setdefault((h, w), []).append((d, var))
                night_days_by_h.setdefault(h, set()).add(d)

        penalty_items = []

        for h in (hh.name for hh in hospitals):
            # その病院で Night に入れる候補者(候補日が min_candidate_nights 以上)
            Wh = [
                w
                for (hh, w) in hw_vars
                if hh == h and len(hw_vars[(h, w)]) >= self.min_candidate_nights
            ]
            Kh = len(Wh)
            days_h = sorted(night_days_by_h.get(h, []))
            if Kh <= 1 or not days_h:
                continue

            # 総勤務回数 T_h と平均 A_h
            Th = len(days_h)  # 重み付けなしカウント
            Ah = Th / Kh
            Lh = int(Ah)  # floor
            Uh = Lh + 1  # ceil

            # 各人の勤務回数
            counts = {}
            for w in Wh:
                terms = [var for (_, var) in hw_vars[(h, w)]]
                counts[w] = pulp.lpSum(terms) if terms else pulp.lpSum([])

            # バンド外だけペナルティ
            for w in Wh:
                over = pulp.LpVariable(f"night_count_diff_over_{h}_{w}", lowBound=0)
                under = pulp.LpVariable(f"night_count_diff_under_{h}_{w}", lowBound=0)
                model += over >= counts[w] - Uh
                model += under >= Lh - counts[w]

                penalty_items.append(
                    (over, self.weight, {"hospital": h, "worker": w, "kind": "over"})
                )
                penalty_items.append(
                    (under, self.weight, {"hospital": h, "worker": w, "kind": "under"})
                )

        add_penalties(ctx, self.name, penalty_items)


register(SoftNightCountMaxDiff())
