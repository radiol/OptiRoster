# ConstraintBase Template Method Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ConstraintBase.apply()` を Template Method に変え、`requires` チェックを自動強制する。

**Architecture:** `apply()` を具体メソッド化し `ensure_requires()` 呼び出し後に抽象メソッド `_apply()` へ委譲する。全サブクラスは `apply` → `_apply` にリネームするだけで対応完了。

**Tech Stack:** Python 3.12+, PuLP, uv, pytest

---

### Task 1: 失敗するテストを書く

**Files:**
- Create: `tests/test_base_impl.py`

- [ ] **Step 1: テストファイルを作成する**

```python
# tests/test_base_impl.py
from typing import ClassVar

import pulp
import pytest

from src.constraints.base_impl import ConstraintBase
from src.domain.context import VarKey


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
    with pytest.raises(RuntimeError, match="dummy.*foo"):
        c.apply(model, {}, {})  # ctx に "foo" がない


def test_apply_succeeds_when_requires_satisfied() -> None:
    """requires を満たした ctx では apply() が正常終了する"""
    c = _DummyConstraint()
    model = pulp.LpProblem("test")
    c.apply(model, {}, {"foo": "bar"})  # raises しないこと
```

- [ ] **Step 2: テストが失敗することを確認する**

```bash
uv run pytest tests/test_base_impl.py -v
```

期待: `TypeError: Can't instantiate abstract class _DummyConstraint`
(`_apply` はまだ抽象メソッドとして存在しないため)

---

### Task 2: base_impl.py を Template Method に変更する

**Files:**
- Modify: `src/constraints/base_impl.py`

- [ ] **Step 1: base_impl.py を更新する**

`src/constraints/base_impl.py` を以下に置き換える:

```python
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
        """モデルに制約を追加する (サブクラスで実装)"""
        pass
```

- [ ] **Step 2: テストが通ることを確認する**

```bash
uv run pytest tests/test_base_impl.py -v
```

期待: 2テストとも PASS

---

### Task 3: c01〜c07 の apply → _apply リネーム

**Files:**
- Modify: `src/constraints/c01_one_person_per_hospital.py`
- Modify: `src/constraints/c02_no_overlap_same_time.py`
- Modify: `src/constraints/c03_respect_preferences.py`
- Modify: `src/constraints/c04_max_assignments_per_worker_hospital.py`
- Modify: `src/constraints/c05_night_spacing.py`
- Modify: `src/constraints/c06_forbid_remote_after_night.py`
- Modify: `src/constraints/c07_univ_last_holiday_night_specialist.py`

- [ ] **Step 1: c01 を更新する**

`src/constraints/c01_one_person_per_hospital.py` の変更点:
1. `def apply(` → `def _apply(`
2. `self.ensure_requires(ctx)` の行を削除 (基底クラスが担うため)

変更後のメソッドシグネチャと冒頭:
```python
    @override
    def _apply(
        self, model: pulp.LpProblem, x: Mapping[VarKey, pulp.LpVariable], ctx: Context
    ) -> None:
        # 各病院が必要な (病院, 日) ごとに、1人だけ割り当てる。
        required_hd = ctx["required_hd"]  # set((h,d), ...)
```

- [ ] **Step 2: c02〜c07 を更新する**

各ファイルで `def apply(` を `def _apply(` にリネームする。
(`self.ensure_requires(ctx)` の呼び出しは c01 以外には存在しないので削除不要)

c02: `src/constraints/c02_no_overlap_same_time.py`
c03: `src/constraints/c03_respect_preferences.py`
c04: `src/constraints/c04_max_assignments_per_worker_hospital.py`
c05: `src/constraints/c05_night_spacing.py`
c06: `src/constraints/c06_forbid_remote_after_night.py`
c07: `src/constraints/c07_univ_last_holiday_night_specialist.py`

- [ ] **Step 3: c01〜c07 のテストが通ることを確認する**

```bash
uv run pytest tests/test_c01_one_person_per_hospital.py tests/test_c02_no_overlap_same_time.py tests/test_c03_respect_preferences.py tests/test_c04_max_assignments.py tests/test_c05_night_spacing.py tests/test_c06_forbid_remote_after_night.py tests/test_c07_univ_last_holiday_night_specialist_only.py -v
```

期待: 全テスト PASS

- [ ] **Step 4: コミットする**

```bash
git add src/constraints/base_impl.py src/constraints/c01_one_person_per_hospital.py src/constraints/c02_no_overlap_same_time.py src/constraints/c03_respect_preferences.py src/constraints/c04_max_assignments_per_worker_hospital.py src/constraints/c05_night_spacing.py src/constraints/c06_forbid_remote_after_night.py src/constraints/c07_univ_last_holiday_night_specialist.py tests/test_base_impl.py
git commit -m "refactor: apply Template Method to ConstraintBase, auto-enforce requires check"
```

---

### Task 4: s01〜s09 の apply → _apply リネーム

**Files:**
- Modify: `src/constraints/s01_night_spacing_pairs.py`
- Modify: `src/constraints/s02_soft_no_night_remote_daypm_same_day.py`
- Modify: `src/constraints/s03_night_deviation_band.py`
- Modify: `src/constraints/s04_soft_balance_non_night_by_weekday.py`
- Modify: `src/constraints/s05_soft_no_duty_after_night.py`
- Modify: `src/constraints/s06_night_count_max_diff.py`
- Modify: `src/constraints/s07_soft_no_consecutive_holiday_duty.py`
- Modify: `src/constraints/s08_soft_no_consecutive_remote.py`
- Modify: `src/constraints/s09_univ_night_weighted_count.py`

- [ ] **Step 1: s01〜s09 を更新する**

各ファイルで `def apply(` を `def _apply(` にリネームする。

s01: `src/constraints/s01_night_spacing_pairs.py`
s02: `src/constraints/s02_soft_no_night_remote_daypm_same_day.py`
s03: `src/constraints/s03_night_deviation_band.py`
s04: `src/constraints/s04_soft_balance_non_night_by_weekday.py`
s05: `src/constraints/s05_soft_no_duty_after_night.py`
s06: `src/constraints/s06_night_count_max_diff.py`
s07: `src/constraints/s07_soft_no_consecutive_holiday_duty.py`
s08: `src/constraints/s08_soft_no_consecutive_remote.py`
s09: `src/constraints/s09_univ_night_weighted_count.py`

- [ ] **Step 2: s01〜s09 のテストが通ることを確認する**

```bash
uv run pytest tests/test_s01_night_spacing_pairs.py tests/test_s02_soft_no_night_remote_daypm_same_day.py tests/test_s03_night_deviation_band.py tests/test_s04_soft_balance_non_night_by_weekday.py tests/test_s05_soft_no_duty_after_night.py tests/test_s06_night_count_max_diff.py tests/test_s07_soft_no_consecutive_holiday_duty.py tests/test_s08_soft_no_consecutive_remote.py tests/test_s09_univ_night_weighted_count.py -v
```

期待: 全テスト PASS

- [ ] **Step 3: コミットする**

```bash
git add src/constraints/s01_night_spacing_pairs.py src/constraints/s02_soft_no_night_remote_daypm_same_day.py src/constraints/s03_night_deviation_band.py src/constraints/s04_soft_balance_non_night_by_weekday.py src/constraints/s05_soft_no_duty_after_night.py src/constraints/s06_night_count_max_diff.py src/constraints/s07_soft_no_consecutive_holiday_duty.py src/constraints/s08_soft_no_consecutive_remote.py src/constraints/s09_univ_night_weighted_count.py
git commit -m "refactor: rename apply -> _apply in s01-s09 soft constraints"
```

---

### Task 5: 全テスト実行で最終確認

- [ ] **Step 1: 全テストを実行する**

```bash
uv run pytest -v
```

期待: 全テスト PASS (新規テスト含む)

- [ ] **Step 2: mypy と ruff を確認する**

```bash
uv run mypy src/constraints/
uv run ruff check src/constraints/
```

期待: エラーなし
