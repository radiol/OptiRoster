from collections import defaultdict
from typing import Any

import pulp

from src.domain.context import Context


def summarize_penalties(
    ctx: Context, sources: list[str] | None = None
) -> tuple[float, dict[str, float], list[dict[str, Any]]]:
    """
    ctx["penaltcies"] を集計して (total, by_source, rows) を返す。
    rows は {"source","var","value","weight","penalty",**meta} の辞書列。
    """
    rows = []
    total = 0.0
    by_source: dict[str, float] = defaultdict(float)

    for penalty_item in ctx.get("penalties", []):
        if sources and penalty_item.source not in sources:
            continue
        z = penalty_item.var
        w = float(penalty_item.weight)
        v = pulp.value(z)
        p = w * v
        total += p
        by_source[penalty_item.source] += p
        row = {
            "source": penalty_item.source,
            "var": z.name,
            "value": v,
            "weight": w,
            "penalty": p,
            **(penalty_item.meta or {}),
        }
        rows.append(row)

    return total, dict(by_source), rows
