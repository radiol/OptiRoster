# 制約システム アーキテクチャ

このドキュメントでは、勤務表自動生成アプリケーションで使用されているプラグインベース制約システムのアーキテクチャについて詳しく説明します。

## 概要

制約システムは、最適化制約のモジュラー追加と削除を可能にするプラグインアーキテクチャを実装しています。このシステムは、ハード制約（満たされなければならない）とソフト制約（最適化目標）を分離しつつ、制約管理のための統一されたインターフェースを提供します。

## アーキテクチャコンポーネント

### 1. レジストリパターン (`base.py`)

コア レジストリシステムは制約の登録と発見を管理します：

```python
constraint_registry = []  # グローバル制約レジストリ

def register(constraint: ConstraintBase) -> None:
    """最適化で使用するための制約インスタンスを登録"""
    constraint_registry.append(constraint)

def all_constraints() -> list[ConstraintBase]:
    """登録されたすべての制約を取得"""
    return list(constraint_registry)
```

**主な機能：**

- 制約発見のためのグローバルレジストリ
- ランタイム制約登録
- 制約インスタンス用のシンプルなリストベースストレージ

### 2. 基底制約インターフェース (`base_impl.py`)

すべての制約は`ConstraintBase`抽象クラスを実装します：

```python
class ConstraintBase(ABC):
    name: str = "unnamed"                    # 制約識別子
    summary: str = "no summary"              # 人間が読みやすい説明
    requires: ClassVar[set[str]] = set()     # 必要なコンテキストキー

    def ensure_requires(self, ctx: Mapping[str, Any]) -> None:
        """必要なコンテキストキーが存在することを検証"""
        miss = self.requires - set(ctx.keys())
        if miss:
            raise RuntimeError(f"{self.name}: missing ctx keys: {sorted(miss)}")

    @abstractmethod
    def apply(
        self,
        model: pulp.LpProblem,              # PuLP最適化モデル
        x: Mapping[VarKey, pulp.LpVariable], # 決定変数
        ctx: Context,                        # 最適化コンテキスト
    ) -> None:
        """最適化モデルに制約を追加"""
        pass
```

**設計原則：**

- **抽象インターフェース**: 一貫した制約実装を保証
- **コンテキスト検証**: 必要なデータ依存関係の自動検証
- **型安全性**: 最適化コンポーネントの強い型付け
- **名前ベース識別**: デバッグ用の各制約固有名

### 3. 自動インポートシステム (`autoimport.py`)

制約モジュールの自動発見と読み込み：

```python
def auto_import_all() -> None:
    """すべての制約モジュールを自動的にインポート"""
    from . import __path__ as pkg_path

    for m in pkgutil.iter_modules(pkg_path):
        name = m.name
        if name.startswith("_"):
            continue
        if name in {"base", "base_impl", "autoimport"}:
            continue
        importlib.import_module(f"src.constraints.{name}")
```

**機能：**

- **ゼロ設定**: 手動の制約登録が不要
- **モジュール発見**: 制約モジュールを自動的に発見
- **選択的インポート**: 内部/ユーティリティモジュールをスキップ
- **プラグイン読み込み**: 真のプラグインアーキテクチャを可能にする

## 制約実装パターン

### ハード制約の例

```python
from .base import register
from .base_impl import ConstraintBase

class OnePersonPerHospital(ConstraintBase):
    name = "one_person_per_hospital"
    summary = "必要な(病院, 日)ごとに勤務者は1人"
    requires: ClassVar[set[str]] = {"required_hd"}  # 依存関係

    @override
    def apply(
        self,
        model: pulp.LpProblem,
        x: Mapping[VarKey, pulp.LpVariable],
        ctx: Context
    ) -> None:
        self.ensure_requires(ctx)  # 依存関係を検証

        required_hd = ctx["required_hd"]  # コンテキストデータを抽出
        by_hd = defaultdict(list)

        # 病院-日付で変数をグループ化
        for (h, _, d, _), var in x.items():
            by_hd[(h, d)].append(var)

        # 制約を追加：必要な各日付の各病院に正確に1人
        for h, d in required_hd:
            vars_hd = by_hd.get((h, d), [])
            model += pulp.lpSum(vars_hd) == 1, f"one_person_{h}_{d.strftime('%Y%m%d')}"

# モジュールがインポートされるときの自動登録
register(OnePersonPerHospital())
```

## 制約カテゴリ

### ハード制約 (c##\_接頭辞)

有効な解に対して満たされなければならない：

- `c01_one_person_per_hospital`: 各病院-日付に正確に1人が必要
- `c02_no_overlap_same_time`: 同時刻の同一人物への複数割り当て禁止
- `c03_respect_preferences`: 勤務者の希望を尊重（利用不可マークを絶対に守る）
- `c04_max_assignments_per_worker_hospital`: 勤務者ごと病院ごとの割り当て上限
- `c05_night_spacing`: 当直間の最小間隔
- `c06_forbid_remote_after_night`: 当直後の遠隔地割り当て禁止
- `c07_univ_last_holiday_night_specialist`: 大学病院の休日当直には専門医が必要

### ソフト制約 (s##\_接頭辞)

ペナルティ付きの最適化目標：

- `s01_night_spacing_pairs`: 当直間隔の最大化
- `s02_soft_no_night_remote_daypm_same_day`: 同日の当直+遠隔地回避
- `s03_night_deviation_band`: 当直割り当ての均等化
- `s04_soft_balance_non_night_by_weekday`: 曜日別割り当ての均等化
- `s05_soft_no_duty_after_night`: 当直翌日の外勤(Day/AM)割り当てを回避

## コンテキストシステム統合

### コンテキストキー

制約システムは型付きコンテキストシステムを使用します：

```python
@dataclass
class Context:
    hospitals: list[Hospital]
    workers: list[Worker]
    required_hd: set[tuple[str, date]]  # 必要な(病院, 日付)ペア
    # ... その他のコンテキストデータ
```

### VarKeyシステム

決定変数は構造化キーでインデックスされます：

```python
VarKey = tuple[str, str, date, ShiftType]  # (病院, 勤務者, 日付, シフト)
```

## プラグインライフサイクル

```mermaid
graph TD
    A[アプリケーション開始] --> B[auto_import_all\(\)]
    B --> C[制約モジュール読み込み]
    C --> D[モジュールインポートがregister\(\)をトリガー]
    D --> E[制約インスタンスがレジストリに追加]
    E --> F[最適化フェーズ]
    F --> G[all_constraints\(\)がリストを返す]
    G --> H[各制約をモデルに適用]
    H --> I[最適化問題を解決]
```

## 新しい制約の追加

### 1. 制約モジュールの作成

```python
# src/constraints/c08_my_new_constraint.py
from .base import register
from .base_impl import ConstraintBase

class MyNewConstraint(ConstraintBase):
    name = "my_new_constraint"
    requires: ClassVar[set[str]] = {"workers", "hospitals"}

    @override
    def apply(self, model, x, ctx):
        self.ensure_requires(ctx)
        # ここに制約ロジックを追加
        pass

register(MyNewConstraint())
```

### 2. 自動発見

制約は、アプリケーション開始時に自動的に発見され、読み込まれます。

### 3. テスト

```python
# tests/test_my_new_constraint.py
def test_my_new_constraint():
    constraint = MyNewConstraint()
    # 制約ロジックのテスト
    assert constraint.name == "my_new_constraint"
```

## 設計の利点

### モジュラー性

- 各制約は自己完結している
- 制約の追加/削除が容易
- 関心の明確な分離

### 拡張性

- プラグインベースアーキテクチャ
- コアシステムの修正が不要
- ハード制約とソフト制約の両方をサポート

### 保守性

- すべての制約にわたる一貫したインターフェース
- 自動依存関係検証
- 明確な命名規則

### テスト可能性

- 個別制約テスト
- テストでのレジストリ分離
- コンテキストを通じた依存性注入

## パフォーマンスに関する考慮事項

- **遅延読み込み**: 必要な時のみ制約を読み込み
- **レジストリ効率**: 制約数が少ない場合のシンプルなリストベースレジストリ
- **コンテキスト検証**: 早期検証によりランタイムエラーを防止
- **メモリ使用量**: 制約インスタンスは軽量

## オプティマイザーとの統合

制約システムはPuLP最適化フレームワークと統合されます：

1. **モデル作成**: 空のPuLPモデルが作成される
2. **変数生成**: ドメインモデルに基づいて決定変数が作成される
3. **制約適用**: 登録された各制約がモデルにルールを追加する
4. **最適化**: PuLPソルバーが最適解を見つける
5. **結果処理**: 解が抽出され、フォーマットされる

このアーキテクチャは、複雑な最適化制約管理のための堅牢で拡張可能な基盤を提供します。
