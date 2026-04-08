from typing import ClassVar

import pulp
import pytest

from src.constraints.base_impl import ConstraintBase


class _DummyConstraint(ConstraintBase):
    name = "dummy"
    requires: ClassVar[set[str]] = {"foo"}

    def _apply(
        self,
        model: pulp.LpProblem,
        x,
        ctx,
    ) -> None:
        pass


def test_apply_raises_when_required_key_missing() -> None:
    """requires に指定したキーが ctx にない場合、apply() が RuntimeError を送出する"""
    c = _DummyConstraint()
    model = pulp.LpProblem("test")
    with pytest.raises(RuntimeError, match=r"dummy.*foo"):
        c.apply(model, {}, {})  # ctx に "foo" がない


def test_apply_succeeds_when_requires_satisfied() -> None:
    """requires を満たした ctx では apply() が正常終了する"""
    c = _DummyConstraint()
    model = pulp.LpProblem("test")
    c.apply(model, {}, {"foo": "bar"})  # raises しないこと
