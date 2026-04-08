# 大学病院当直の重み付き月間上限ソフト制約 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `is_university=True` の病院における当直(NIGHT)シフトについて、各workerの重み付き月間合計が3を超えた場合に線形ペナルティを課すソフト制約を追加する。

**Architecture:** 新規ファイル `s09_univ_night_weighted_count.py` を作成し、既存の `ConstraintBase` + `add_penalties` パターンに従って実装する。休日は weight=2、平日は weight=1 で加算し、合計が limit(=3) を超えた分に penalty_weight(=3.0) を乗じた線形ペナルティを課す。ファイル末尾の `register()` 呼び出しと `autoimport.py` の自動インポート機構により既存の仕組みで登録される。

**Tech Stack:** Python, PuLP (LP), jpholiday (`is_holiday_or_weekend`), pytest

---

### Task 1: テストファイルを作成する

**Files:**
- Create: `tests/test_s09_univ_night_weighted_count.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# tests/test_s09_univ_night_weighted_count.py
"""s09: 大学病院当直の重み付き月間上限ソフト制約のテスト."""

from __future__ import annotations

import datetime as dt

import pulp
import pytest

from src.domain.types import Hospital, ShiftType
from src.optimizer.objective import set_objective_with_penalties

SOURCE = "soft_univ_night_weighted_count"

UNIV = Hospital(name="大学", is_remote=False, is_university=True, demand_rules=[])
LOCAL = Hospital(name="一般", is_remote=False, is_university=False, demand_rules=[])

# 2025-06-07(土)=休日(weight=2), 2025-06-08(日)=休日(weight=2)
# 2025-06-02(月)=平日(weight=1), 2025-06-03(火)=平日(weight=1)
SAT = dt.date(2025, 6, 7)
SUN = dt.date(2025, 6, 8)
MON = dt.date(2025, 6, 2)
TUE = dt.date(2025, 6, 3)


def _sum_penalties(ctx: dict, source: str = SOURCE) -> float:
    total = 0.0
    for item in ctx.get("penalties", []):
        if getattr(item, "source", None) != source:
            continue
        v = pulp.value(item.var)
        if v is None:
            continue
        total += float(item.weight) * float(v)
    return total


def _fixed(name: str, value: int) -> pulp.LpVariable:
    """固定値のLP変数(value=0 or 1)を返す."""
    return pulp.LpVariable(name, lowBound=value, upBound=value, cat="Integer")


# -- ペナルティが発生するケース --


def test_penalty_when_two_holidays_over_limit(ensure_constraint):
    """休日2回(weight=4) -> over=1, penalty=3.0."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (UNIV.name, "Alice", SUN, ShiftType.NIGHT): _fixed("x_sun", 1),
    }
    m = pulp.LpProblem("s09_over", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, SUN], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 3.0) <= 1e-8


def test_penalty_two_units_over(ensure_constraint):
    """休日2回+平日1回(weight=5) -> over=2, penalty=6.0."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (UNIV.name, "Alice", SUN, ShiftType.NIGHT): _fixed("x_sun", 1),
        (UNIV.name, "Alice", MON, ShiftType.NIGHT): _fixed("x_mon", 1),
    }
    m = pulp.LpProblem("s09_over2", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, SUN, MON], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 6.0) <= 1e-8


def test_multiple_workers_independent_penalties(ensure_constraint):
    """複数workerが各自超過 -> それぞれ独立にペナルティ."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    # Alice: 休日2回(weight=4) -> over=1, penalty=3.0
    # Bob: 休日2回(weight=4) -> over=1, penalty=3.0
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("xa_sat", 1),
        (UNIV.name, "Alice", SUN, ShiftType.NIGHT): _fixed("xa_sun", 1),
        (UNIV.name, "Bob", SAT, ShiftType.NIGHT): _fixed("xb_sat", 1),
        (UNIV.name, "Bob", SUN, ShiftType.NIGHT): _fixed("xb_sun", 1),
    }
    m = pulp.LpProblem("s09_multi", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, SUN], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert abs(_sum_penalties(ctx) - 6.0) <= 1e-8


# -- ペナルティが発生しないケース --


def test_no_penalty_at_limit(ensure_constraint):
    """休日1回(weight=2)+平日1回(weight=1)=3 -> ちょうど上限, ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (UNIV.name, "Alice", MON, ShiftType.NIGHT): _fixed("x_mon", 1),
    }
    m = pulp.LpProblem("s09_limit", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT, MON], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_non_university_not_counted(ensure_constraint):
    """非大学病院のNIGHTはカウントされない -> ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    # LOCAL に3回NIGHT -> 大学病院ではないのでカウントされない
    x = {
        (LOCAL.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
        (LOCAL.name, "Alice", SUN, ShiftType.NIGHT): _fixed("x_sun", 1),
        (LOCAL.name, "Alice", MON, ShiftType.NIGHT): _fixed("x_mon", 1),
    }
    m = pulp.LpProblem("s09_nonuniv", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV, LOCAL], "days": [SAT, SUN, MON], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_no_university_hospitals(ensure_constraint):
    """大学病院がctxに存在しない -> ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    x = {
        (LOCAL.name, "Alice", SAT, ShiftType.NIGHT): _fixed("x_sat", 1),
    }
    m = pulp.LpProblem("s09_no_univ", pulp.LpMaximize)
    ctx: dict = {"hospitals": [LOCAL], "days": [SAT], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8


def test_no_penalty_when_no_night_vars(ensure_constraint):
    """大学病院のNIGHT変数が存在しない -> エラーなし, ペナルティなし."""
    c = ensure_constraint(
        "src.constraints.s09_univ_night_weighted_count",
        SOURCE,
    )
    # DAY シフトのみ
    x = {
        (UNIV.name, "Alice", SAT, ShiftType.DAY): _fixed("x_day", 1),
    }
    m = pulp.LpProblem("s09_no_night", pulp.LpMaximize)
    ctx: dict = {"hospitals": [UNIV], "days": [SAT], "workers": []}
    c.apply(m, x, ctx)
    set_objective_with_penalties(m, pulp.lpSum(x.values()), ctx)

    status = m.solve(pulp.HiGHS(msg=False))
    assert pulp.LpStatus[status] == "Optimal"
    assert _sum_penalties(ctx) <= 1e-8
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```bash
pytest tests/test_s09_univ_night_weighted_count.py -v
```

期待結果: `ImportError` または `ModuleNotFoundError` (s09 モジュールが存在しないため)

- [ ] **Step 3: コミット**

```bash
git checkout -b feat/s09-univ-night-weighted-count
git add tests/test_s09_univ_night_weighted_count.py
git commit -m "test: s09 大学病院当直の重み付き月間上限ソフト制約のテストを追加"
```

---

### Task 2: ソフト制約を実装する

**Files:**
- Create: `src/constraints/s09_univ_night_weighted_count.py`

- [ ] **Step 1: 実装ファイルを作成する**

```python
# src/constraints/s09_univ_night_weighted_count.py
from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, override

import pulp

from src.calendar.utils import is_holiday_or_weekend
from src.constraints.penalty_utils import add_penalties
from src.domain.context import Context, VarKey
from src.domain.types import Hospital, ShiftType

from .base import register
from .base_impl import ConstraintBase


class SoftUnivNightWeightedCount(ConstraintBase):
    """
    大学病院(is_university=True)の当直(NIGHT)について,
    各workerの1ヶ月の重み付き合計回数がlimitを超えた場合に線形ペナルティを課す.
    - 休日(is_holiday_or_weekend=True): holiday_weight カウント(default=2)
    - 平日: weekday_weight カウント(default=1)
    - 超過量 1 単位あたり weight のペナルティ(default=3.0)
    """

    name = "soft_univ_night_weighted_count"
    summary = "大学病院の当直回数を重み付きで月3回以下に制限"
    requires: ClassVar[set[str]] = {"hospitals"}

    def __init__(
        self,
        limit: int = 3,
        holiday_weight: int = 2,
        weekday_weight: int = 1,
        weight: float = 3.0,
    ):
        self.limit = int(limit)
        self.holiday_weight = int(holiday_weight)
        self.weekday_weight = int(weekday_weight)
        self.weight = float(weight)

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context,
    ) -> None:
        hospitals: list[Hospital] = ctx["hospitals"]
        univ_names = {h.name for h in hospitals if h.is_university}
        if not univ_names:
            return

        # worker ごとに大学病院 NIGHT 変数を収集
        # {worker: [(day_weight, var), ...]}
        worker_vars: dict[str, list[tuple[int, pulp.LpVariable]]] = {}
        for (h, w, d, s), var in x.items():
            if h not in univ_names or s != ShiftType.NIGHT:
                continue
            day_weight = self.holiday_weight if is_holiday_or_weekend(d) else self.weekday_weight
            worker_vars.setdefault(w, []).append((day_weight, var))

        penalty_items = []
        for w, wv_list in worker_vars.items():
            weighted_sum = pulp.lpSum(dw * v for dw, v in wv_list)
            over = pulp.LpVariable(f"univ_night_wcount_over_{w}", lowBound=0)
            model += over >= weighted_sum - self.limit
            penalty_items.append(
                (over, self.weight, {"worker": w})
            )

        add_penalties(ctx, self.name, penalty_items)


register(SoftUnivNightWeightedCount())
```

- [ ] **Step 2: テストを実行してすべて通ることを確認する**

```bash
pytest tests/test_s09_univ_night_weighted_count.py -v
```

期待結果: 全テスト PASSED

- [ ] **Step 3: 既存テストが壊れていないことを確認する**

```bash
pytest tests/ -x -q
```

期待結果: 全テスト PASSED (既存テストに影響なし)

- [ ] **Step 4: コミット**

```bash
git add src/constraints/s09_univ_night_weighted_count.py
git commit -m "feat: s09 大学病院当直の重み付き月間上限ソフト制約を追加"
```
