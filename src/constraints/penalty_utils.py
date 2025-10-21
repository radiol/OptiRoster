from typing import Any

import pulp

from src.constraints.penalty_types import PenaltyItem
from src.domain.context import Context


def add_penalties(
    ctx: Context, name: str, penalty_items: list[tuple[pulp.LpVariable, float, Any]]
) -> None:
    """
    penalty_items: List[(LpVariable, weight, meta_dict)]
        - var: 補助変数 (z)
        - weight: ペナルティ係数
        - meta: 任意の辞書 {"worker":..., "date":..., ...}

    ctx["penalties"]のList[PenaltyItem]にPenaltyItemを追加する
    """
    if not penalty_items:
        return
    penalty_items_list = ctx.setdefault("penalties", [])
    for var, weight, meta in penalty_items:
        penalty_items_list.append(PenaltyItem(var=var, weight=weight, meta=meta, source=name))
