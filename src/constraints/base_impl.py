# src/constraints/base_impl.py
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

import pulp

from src.domain.context import Context, VarKey


class ConstraintBase(ABC):
    name: str = "unnamed"
    summary: str = "no summary"
    requires: ClassVar[set[str]] = set()  # ctxに必要なキーの集合("hospitals", "workers"など)

    def ensure_requires(self, ctx: Mapping[str, Any]) -> None:
        miss = self.requires - set(ctx.keys())
        if miss:
            raise RuntimeError(f"{self.name}: missing ctx keys: {sorted(miss)}")

    @abstractmethod
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        """モデルに制約を追加する"""
        pass
