from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType, Weekday

from .base import register
from .base_impl import ConstraintBase
from .penalty_utils import add_penalties


class SoftNonNightBalanceByWeekday(ConstraintBase):
    """
    Night以外(DAY/AM/PM)の割当を「病院 x 曜日 x シフト」単位で均一化するソフト制約。
    対象の (h, weekday, shift) について、その月内の該当日回数 T を
    候補者数 K で割った平均 A=T/K を基準に、各workerの回数 c が
    L=⌊A⌋〜U=⌈A⌉ の範囲に収まるようにペナルティを課す。

    - 重みは全て 1.0(休日ウェイト無し)
    - 候補者が極端に少ないworkerは対象外(min_candidate)
    - その (h, weekday, shift) で変数が1つも無い/候補者が1名以下ならスキップ

    requires: {"hospitals"}
    """

    name = "soft_non_night_balance_by_weekday"
    summary = "病院ごとの日勤の偏りを避ける"
    requires: ClassVar[set[str]] = {"hospitals"}

    def __init__(
        self,
        weight_over: float = 1.0,
        weight_under: float = 1.0,
        min_candidate: int = 0,
        target_shifts: tuple[ShiftType, ...] = (ShiftType.DAY, ShiftType.AM, ShiftType.PM),
    ):
        self.weight_over = float(weight_over)
        self.weight_under = float(weight_under)
        self.min_candidate = int(min_candidate)
        self.target_shifts = tuple(target_shifts)

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        hospitals: list[Hospital] = ctx["hospitals"]

        # VarKey(h, w, d, s) のうち s ∈ target_shifts だけ集約
        # 併せて (h, weekday, s) ごとの対象日集合を作る
        hwds_vars: dict[VarKey, pulp.LpVariable] = {}
        days_by_h_ws: dict[tuple[str, Weekday, ShiftType], list[date]] = {}

        def to_weekday(d: date) -> Weekday:
            # Weekday Enum は月曜=0 ... 日曜=6 の順で定義済み前提
            return list(Weekday)[d.weekday()]

        for var_key, var in x.items():
            h, w, d, s = var_key
            if s in self.target_shifts:
                hwds_vars[var_key] = var
                key = (h, to_weekday(d), s)
                days_by_h_ws.setdefault(key, []).append(d)

        penalty_items = []

        for hosp in hospitals:
            hname = hosp.name
            # 病院ごとに (weekday, s) を走査
            for (hh, weekday, s), days in list(days_by_h_ws.items()):
                if hh != hname:
                    continue
                days = sorted(set(days))
                if not days:
                    continue

                # 候補者集合 Wh(この (h,weekday,s) で min_candidate 以上の候補がある人)
                # 候補数 = その人に対し、対象日 d の x[(h,w,d,s)] が存在する個数
                cand_count_by_w: dict[str, int] = {}
                for h2, w2, d2, s2 in hwds_vars:
                    if h2 == hname and s2 == s and to_weekday(d2) == weekday:
                        cand_count_by_w[w2] = cand_count_by_w.get(w2, 0) + 1
                Wh = [w for w, cnt in cand_count_by_w.items() if cnt >= self.min_candidate]
                Kh = len(Wh)
                if Kh <= 1:
                    continue

                # その (h,weekday,s) の総回数(重み1.0)
                Th = float(len(days))
                Ah = Th / Kh
                Lh = int(Ah)  # floor
                Uh = Lh + 1  # ceil

                # 各 worker の回数 c = Σ_d x[h,w,d,s]
                counts: dict[str, pulp.LpAffineExpression] = {}
                for w in Wh:
                    terms = []
                    for d in days:
                        var = hwds_vars.get(VarKey(hname, w, d, s))
                        if var is not None:
                            terms.append(var)
                    counts[w] = pulp.lpSum(terms) if terms else pulp.lpSum([])

                # over/under 変数を置いてバンド外だけペナルティ
                for w in Wh:
                    over = pulp.LpVariable(
                        f"non_night_dev_over_{hname}_{weekday.value}_{s.value}_{w}", lowBound=0
                    )
                    under = pulp.LpVariable(
                        f"non_night_dev_under_{hname}_{weekday.value}_{s.value}_{w}", lowBound=0
                    )
                    model += over >= counts[w] - Uh
                    model += under >= Lh - counts[w]

                    meta = {
                        "hospital": hname,
                        "weekday": weekday.value,
                        "shift": s.value,
                        "kind": None,  # 後で上書き
                        "T": Th,
                        "K": Kh,
                        "L": Lh,
                        "U": Uh,
                    }
                    pi_over = (over, self.weight_over, {**meta, "kind": "over"})
                    pi_under = (under, self.weight_under, {**meta, "kind": "under"})
                    penalty_items.extend([pi_over, pi_under])

        add_penalties(ctx, self.name, penalty_items)


register(SoftNonNightBalanceByWeekday())
