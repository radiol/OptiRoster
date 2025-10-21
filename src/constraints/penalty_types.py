from typing import Any, NamedTuple

import pulp


class PenaltyItem(NamedTuple):
    var: pulp.LpVariable
    weight: float
    meta: dict[str, Any]  # {"hospital":..., "worker":..., ...}
    source: str  # e.g. "soft_night_deviation_band"
