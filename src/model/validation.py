from collections import defaultdict
from datetime import date

from src.model.demand import compute_required_hd
from src.model.variable_builder import VariableBuilder


def validate_required_has_candidates_or_fail(
    vb: VariableBuilder, specified_days: dict[str, list[int]]
) -> None:
    """需要がある (h,d) に対し、少なくとも1つ UB==1 の候補があるか検証。無ければ例外。"""
    required_hd = compute_required_hd(vb.hospitals, vb.days, vb.weekdays, specified_days)
    # 候補カウント
    cand: dict[tuple[str, date], int] = defaultdict(int)
    for (h, _w, d, _s), ub in vb.ub.items():
        if ub == 1:
            cand[(h, d)] += 1

    missing = [(h, d) for (h, d) in required_hd if cand[(h, d)] == 0]
    if missing:
        lines = [f"- {h} {d.isoformat()}(候補0件)" for h, d in sorted(missing)]
        raise ValueError("需要日に割当候補が存在しません:\n" + "\n".join(lines))
