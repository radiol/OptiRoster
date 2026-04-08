# Design: 大学病院当直の重み付き月間上限ソフト制約

**Date:** 2026-04-08
**Status:** Approved

## 概要

`is_university=True` の病院における当直 (NIGHT) シフトについて、
各個人の1ヶ月の重み付き合計回数が上限 (デフォルト: 3) を超えた場合に
線形ペナルティを課すソフト制約を追加する。

## 要件

- 対象シフト: NIGHT のみ
- 対象病院: `Hospital.is_university == True` のすべて (集約して1人あたりの合計で評価)
- 重み付けルール:
  - 休日 (`is_holiday_or_weekend` が True): 2 カウント
  - 平日: 1 カウント
- 上限: 重み付き合計 <= 3
- ペナルティ: 超過量 1 単位あたり 3.0 (線形)

## 実装ファイル

新規: `src/constraints/s09_univ_night_weighted_count.py`

## クラス設計

```python
class SoftUnivNightWeightedCount(ConstraintBase):
    name = "soft_univ_night_weighted_count"
    summary = "大学病院の当直回数を重み付きで月3回以下に制限"
    requires = {"hospitals", "days", "workers"}

    def __init__(
        self,
        limit: int = 3,
        holiday_weight: int = 2,
        weekday_weight: int = 1,
        weight: float = 3.0,
    ):
        ...
```

## LP モデル

各 worker `w` について:

1. `univ = {h.name for h in ctx["hospitals"] if h.is_university}`
2. `w_d = 2 if is_holiday_or_weekend(d) else 1` を各日付に対して事前計算
3. `weighted_sum_w = lpSum(w_d * x[h,w,d,NIGHT] for h in univ, d in days)`
4. `over_w = LpVariable(f"univ_night_wcount_over_{w}", lowBound=0)`
5. `model += over_w >= weighted_sum_w - limit`
6. `add_penalties(ctx, name, [(over_w, weight, {"worker": w})])`

大学病院の NIGHT 変数が存在しない worker はスキップ。

## 登録

ファイル末尾で `register(SoftUnivNightWeightedCount())` を呼び出す。
`autoimport.py` の自動インポートにより既存の仕組みで登録される。

## テスト方針

- 休日1回 (weight=2) + 平日1回 (weight=1) = 3 → ペナルティなし
- 休日2回 (weight=4) → over=1, ペナルティ=3.0
- 大学病院の NIGHT シフトがない worker → 変数・制約ともに生成しない
