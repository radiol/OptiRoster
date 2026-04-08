# src/constraints/base_impl.py
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, ClassVar

import pulp

from src.domain.context import Context, VarKey


class ConstraintBase(ABC):
    name: str = "unnamed"
    summary: str = "no summary"
    requires: ClassVar[set[str]] = set()  # ctx に必要なキーの集合("hospitals", "workers" など)

    def ensure_requires(self, ctx: Mapping[str, Any]) -> None:
        miss = self.requires - set(ctx.keys())
        if miss:
            raise RuntimeError(f"{self.name}: missing ctx keys: {sorted(miss)}")

    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        """テンプレートメソッド: requires 検証後に _apply() を呼ぶ"""
        self.ensure_requires(ctx)
        self._apply(model, x, ctx)

    @abstractmethod
    def _apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        """モデルに制約を追加する (サブクラスで実装)。
        このメソッドが呼ばれる時点では ensure_requires() による検証は完了している。"""
        pass
