# Design: ConstraintBase requires を Template Method で強制適用

Date: 2026-04-08

## 背景

`ConstraintBase` には `requires` (ClassVar[set[str]]) と `ensure_requires()` が定義されており、
各制約が ctx に必要なキーを宣言する仕組みが存在する。
しかし `ensure_requires()` を `apply()` 内で実際に呼んでいるのは `c01` のみであり、
他の制約では requires が「設計ドキュメント」として機能するに留まっていた。
これにより、新規制約追加時や ctx 構造変更時に missing key エラーが検出されないリスクがある。

## 目標

- `requires` の宣言が自動的にランタイム検証として機能するようにする
- 新規制約を追加した際、`ensure_requires()` の呼び忘れが起きない構造にする
- 外部インターフェース (`apply()`) は変更しない

## 設計

### Template Method パターンの適用

`ConstraintBase` の `apply()` を具体メソッドに変更し、
サブクラスの実装は `_apply()` に移動する。

```
apply() [concrete, base class]
  └─ ensure_requires(ctx)   # requires チェック
  └─ _apply(model, x, ctx)  # abstract, サブクラスが実装
```

### base_impl.py の変更

```python
class ConstraintBase(ABC):
    name: str = "unnamed"
    summary: str = "no summary"
    requires: ClassVar[set[str]] = set()

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

### 各制約ファイルの変更

対象14ファイル: c01〜c07, s01〜s09

- `def apply(` → `def _apply(` にリネーム
- c01 の `self.ensure_requires(ctx)` 呼び出しを削除 (基底クラスが担うため)

### 呼び出し元 (変更なし)

- `cli/main.py`: `c.apply(model, x, ctx)` のまま
- `gui/main_window.py`: `c.apply(model, x, ctx)` のまま

## 影響範囲

| ファイル | 変更内容 |
|---|---|
| `src/constraints/base_impl.py` | `apply()` を具体メソッド化、`_apply()` abstract 追加 |
| `src/constraints/c01_one_person_per_hospital.py` | `apply` → `_apply` リネーム、`ensure_requires` 呼び出し削除 |
| `src/constraints/c02〜c07_*.py` (6ファイル) | `apply` → `_apply` リネーム |
| `src/constraints/s01〜s09_*.py` (7ファイル) | `apply` → `_apply` リネーム |
| `src/cli/main.py` | 変更なし |
| `src/gui/main_window.py` | 変更なし |

## テスト方針

- 既存テストがそのまま通ることを確認 (`uv run pytest`)
- `requires` に存在しないキーを指定した制約を作り、`apply()` が `RuntimeError` を送出することを確認
