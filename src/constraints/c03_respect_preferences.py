from collections.abc import Mapping
from typing import ClassVar, override

import pulp

from src.domain.context import Context, VarKey
from src.io.preferences_loader import disallowed_shifts_for

from .base import register
from .base_impl import ConstraintBase


class RespectPreferencesFromCSV(ConstraintBase):
    """
    勤務希望(可否)CSVをハード制約で反映する。
    - status=当直不可        → NIGHT を禁止
    - status=日勤・当直不可   → 全シフト禁止
    - 空欄/その他             → 制限なし
    ctx に "preferences" として Dict[(worker: str, date: date), PreferenceStatus] を渡すこと。
    """

    name = "respect_preferences_from_csv"
    summary = "勤務希望.CSVの内容を遵守"
    requires: ClassVar[set[str]] = {"preferences"}  # ctx 依存

    @override
    def apply(
        self, model: pulp.LpProblem, x: Mapping[VarKey, pulp.LpVariable], ctx: Context
    ) -> None:
        pref = ctx.get("preferences", {})
        for (h, w, d, s), var in x.items():
            status = pref.get((w, d))
            if status is None:
                continue
            disallowed = disallowed_shifts_for(status)
            if s in disallowed:
                model += (
                    var == 0,
                    f"pref_forbid_{h}_{w}_{d.strftime('%Y%m%d')}_{s.name}",
                )


register(RespectPreferencesFromCSV())
