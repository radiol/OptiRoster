# 勤務表自動生成システム ユーザーガイド

最適な病院勤務スケジュールを自動作成するための勤務表自動生成システムの設定と使用に関する包括的なガイドです。

## クイックスタート

### 前提条件

- Python 3.11+ がインストールされていること
- `uv` パッケージマネージャー (`pip install uv` または `brew install uv`)

### インストール

```bash
# クローンとセットアップ
git clone <リポジトリURL>
cd OptiRoster
uv sync
```

### 基本的な使用方法

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv \
  --xlsx output/schedule-2025-10.xlsx
```

## 設定ファイル

### 1. 病院設定 (`config/hospitals.toml`)

病院の特性とスタッフ配置要件を定義します：

```toml
[[hospitals]]
name = "中央病院"
is_remote = false
is_university = false

[[hospitals.demand_rules]]
shift_type = "当直"
weekdays = ["金曜", "土曜"]
frequency = "毎週"

[[hospitals]]
name = "遠隔クリニック"
is_remote = true
is_university = false

[[hospitals.demand_rules]]
shift_type = "日勤"
weekdays = ["月曜", "水曜", "金曜"]
frequency = "毎週"
```

**病院属性：**

- `name`: 病院の一意な識別子
- `is_remote`: 遠隔地の場合は`true`（当直後勤務ルールに影響）
- `is_university`: 大学病院の場合は`true`（専門医要件）

**需要ルール：**

- `shift_type`: `"日勤"` (日勤), `"当直"` (当直), `"AM"`, `"PM"`
- `weekdays`: `["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]`
- `frequency`: `"毎週"` (毎週), `"隔週"` (隔週), `"指定日"` (特定日)

### 2. 勤務者設定 (`config/workers.toml`)

勤務者の能力と利用可能性を定義します：

```toml
[[workers]]
name = "田中医師"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "中央病院"
weekdays = ["月曜", "金曜"]
shift_type = "当直"

[[workers.assignments]]
hospital = "中央病院"
weekdays = ["火曜", "水曜", "木曜"]
shift_type = "日勤"

[[workers]]
name = "佐藤医師"
is_diagnostic_specialist = false

[[workers.assignments]]
hospital = "遠隔クリニック"
weekdays = ["月曜", "水曜", "金曜"]
shift_type = "日勤"
```

**勤務者属性：**

- `name`: 勤務者の一意な識別子
- `is_diagnostic_specialist`: 大学病院の休日当直に必要

**割り当てルール：**

- `hospital`: 勤務者が割り当て可能な病院
- `weekdays`: 勤務者が利用可能な曜日
- `shift_type`: 勤務者が対応可能なシフト種類

### 3. 指定日 (`data/specified-YYYY-MM.toml`)

特別な要件がある特定の日付をオーバーライドします：

```toml
# 祝日や特別な日付
[[specified_days]]
hospital = "大学病院"
date = 2025-10-10  # 祝日
shift_type = "当直"
```

### 4. 勤務希望 (`data/YYYY-MM.csv`)

特定の日付に対する勤務者の希望：

```csv
name,date,shift_type,preference
田中医師,2025-10-01,当直,可
田中医師,2025-10-02,日勤,不可
佐藤医師,2025-10-15,日勤,希望
佐藤医師,2025-10-20,当直,不可
```

**希望値：**

- `希望` (希望): 割り当てへのソフトな希望
- `可` (利用可能): 中立的な利用可能性
- `不可` (利用不可): 割り当てに対するハード制約

### 5. 最大割り当て数 (`data/max-assignments.csv`)

勤務者ごと病院ごとの割り当て上限：

```csv
worker,hospital,max_assignments
田中医師,中央病院,8
田中医師,大学病院,4
佐藤医師,遠隔クリニック,10
```

## コマンドラインインターフェース

### 必須引数

- `--year YYYY`: スケジュール生成の対象年
- `--month MM`: 対象月 (1-12)
- `--specified-days PATH`: 指定日TOMLファイルへのパス
- `--preferences PATH`: 希望CSVファイルへのパス

### オプション引数

- `--hospitals PATH`: 病院設定 (デフォルト: `config/hospitals.toml`)
- `--workers PATH`: 勤務者設定 (デフォルト: `config/workers.toml`)
- `--max-assignments-csv PATH`: 最大割り当て数 (デフォルト: `data/max-assignments.csv`)
- `--xlsx PATH`: Excel出力ファイルパス
- `--json`: フォーマットされたテキストの代わりにJSON出力

### 例

**基本的な月次スケジュール：**

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv
```

**Excel出力付き：**

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv \
  --xlsx schedules/october-2025.xlsx
```

**統合用JSON出力：**

```bash
uv run -m src.cli.main \
  --year 2025 --month 10 \
  --specified-days data/specified-2025-10.toml \
  --preferences data/2025-10.csv \
  --json > results.json
```

## 出力の理解

### コンソール出力

システムは以下を示すリッチフォーマット出力を提供します：

1. **解決サマリー：**
   - ステータス: 最適、実行不可能、またはその他のソルバー状態
   - 目的値: 総割り当て数 + ペナルティ調整
   - 解決時間: 最適化にかかった時間

2. **ペナルティレポート：**
   - 制約種類別にグループ化された総ペナルティのサマリーテーブル
   - メタデータ付きの個別ペナルティ項目の内訳
   - スケジューリング競合と制約違反の識別に役立つ
   - より理解しやすい人間が読みやすい制約説明を表示

3. **割り当てスケジュール：**
   - 日付順の割り当て一覧
   - フォーマット: 日付 | 病院 | 勤務者 | シフト

### ペナルティレポートの解釈

ペナルティレポートは制約違反と最適化のトレードオフに関する詳細な洞察を提供します：

#### サマリーセクション

```
                              Penalty Summary                               
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 制約                                    ┃ 合計                          ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ 夜勤間隔を空けたい                      ┃ 15.450                        ┃
┃ 勤務希望.CSVの内容を遵守                ┃ 8.000                         ┃
┃ 平日の非夜勤のバランス                  ┃ 3.200                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

- **総ペナルティ**: 重要度で重み付けされたすべての制約違反の合計
- **制約別**: どの制約がペナルティに最も貢献しているかを示す内訳
- **人間が読みやすい説明**: 各制約の機能を日本語で説明

#### 詳細セクション

```
                                  Penalty Items (Top 30)                                   
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ # ┃ 制約                       ┃ 変数                          ┃ 値  ┃ 重み   ┃ ペナルティ┃ メタ   ┃
┣━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━╋━━━━━━━━╋━━━━━━━━╋━━━━━━━━━┫
┃ 1 ┃ 夜勤間隔を空けたい         ┃ night_spacing_violation_Dr... ┃ 2.0 ┃ 5.0    ┃ 10.0   ┃ w=Dr... ┃
┃ 2 ┃ 勤務希望.CSVの内容を遵守   ┃ preference_violation_2025...  ┃ 1.0 ┃ 8.0    ┃ 8.0    ┃ d=10/15 ┃
┗━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┻━━━━━┻━━━━━━━━┻━━━━━━━━┻━━━━━━━━━┛
```

- **#**: ペナルティの重要度による順位
- **制約**: 人間が読みやすい制約説明
- **変数**: 最適化変数名（技術的識別子）
- **値**: 変数値（違反の程度）
- **重み**: この違反に適用されるペナルティ重み
- **ペナルティ**: 最終ペナルティスコア（値 × 重み）
- **メタ**: 追加コンテキスト（勤務者名、日付など）

#### 最適化のためのペナルティレポートの使用

1. **高い総ペナルティ**: 制約や入力データの調整を検討
2. **制約の不均衡**: 1つの制約が支配的な場合、その重要度を確認
3. **繰り返し違反**: 頻繁に現れる勤務者や日付に注意が必要かも
4. **ゼロペナルティ**: 制約違反のない最適解を示す

### Excel出力

`--xlsx` が指定された場合、以下を含むフォーマットされたExcelファイルを生成します：

- 割り当てのカレンダービュー
- 病院ベースのワークシート
- 統計サマリー
- 制約違反レポート

## 最適化プロセス

### ハード制約（満たされなければならない）

1. **病院ごと日ごとに1人**: 必要な各病院-日付に正確に1つの割り当て
2. **重複割り当てなし**: 勤務者は同時に複数の場所にいることはできない
3. **希望の尊重**: "不可"希望を絶対的に尊重
4. **最大割り当て数**: 勤務者ごと病院ごとの上限を強制
5. **当直間隔**: 当直間の最小間隔
6. **当直後制限**: 当直後の遠隔地割り当てなし
7. **専門医要件**: 大学病院の休日当直には専門医が必要

### ソフト制約（最適化目標）

1. **当直間隔最適化**: 当直間の間隔を最大化
2. **負荷分散**: 割り当てを均等に分散
3. **曜日別分散**: 曜日全体での均等分散
4. **希望最適化**: "希望"割り当てを優先

## トラブルシューティング

### よくある問題

**実行不可能な解：**

- 必要なカバレッジに対する勤務者利用可能性が不十分
- 競合するハード制約
- 過度な"不可"マーキングの希望を確認
- 勤務者割り当てルールが必要な病院/シフトをカバーしているか確認

**最適でない結果：**

- ソースコード内のソフト制約重みを確認
- 勤務者利用可能性ウィンドウを調整
- 専門医対一般勤務者の比率のバランス

**パフォーマンス問題：**

- 大きな勤務者/病院の組み合わせは複雑度を増加
- 四半期ではなく月次最適化期間を検討
- 実装での制約複雑度を確認

### デバッグ手順

1. **入力ファイルの検証：**

   ```bash
   # TOML構文をチェック
   python -c "import tomllib; print(tomllib.load(open('config/hospitals.toml', 'rb')))"

   # CSV形式をチェック
   head -5 data/preferences.csv
   ```

2. **最小データでのテスト：**
   - 2-3人の勤務者と2-3の病院から開始
   - 徐々に複雑度を追加

3. **制約違反の確認：**
   - 高いペナルティソースのペナルティレポートをチェック
   - 個別制約ロジックを検討

## 高度な使用方法

### カスタム制約

`src/constraints/`にファイルを作成して新しい制約を追加：

```python
# src/constraints/c08_custom_rule.py
from .base import register
from .base_impl import ConstraintBase

class CustomRule(ConstraintBase):
    name = "custom_rule"
    requires: ClassVar[set[str]] = {"workers", "hospitals"}

    def apply(self, model, x, ctx):
        # ここに制約ロジックを追加
        pass

register(CustomRule())
```

### バッチ処理

複数月の処理：

```bash
for month in {1..12}; do
  uv run -m src.cli.main \
    --year 2025 --month $month \
    --specified-days data/specified-2025-$(printf "%02d" $month).toml \
    --preferences data/2025-$(printf "%02d" $month).csv \
    --xlsx output/schedule-2025-$(printf "%02d" $month).xlsx
done
```

### 統合

**JSON出力処理：**

```python
import json
import subprocess

result = subprocess.run([
    "uv", "run", "-m", "src.cli.main",
    "--year", "2025", "--month", "10",
    "--specified-days", "data/specified-2025-10.toml",
    "--preferences", "data/2025-10.csv",
    "--json"
], capture_output=True, text=True)

schedule = json.loads(result.stdout)
# スケジュールデータを処理...
```

## ベストプラクティス

### データ管理

- 設定ファイルにバージョン管理を使用
- 月次データファイルの命名規則を維持
- タイムスタンプ付きで生成されたスケジュールをバックアップ

### 設定

- 保守的な制約パラメータから開始
- 限定されたデータセットで新しい設定をテスト
- カスタム制約の変更を文書化

### 品質保証

- スケジュール変更のデプロイ前にテストを実行
- 重要な期間について生成されたスケジュールを手動で検証
- 予期しない制約違反についてペナルティレポートを監視

### パフォーマンス

- より長い期間ではなく月次で最適化
- 解決時間への勤務者/病院数の影響を考慮
- 自動処理ワークフローにはJSON出力を使用
