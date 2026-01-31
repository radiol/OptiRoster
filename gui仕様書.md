0. ゴール概要
   目的

GUI（Qt）内の責務を分割し、設定編集を 独立した Editor Window として切り出す。

メイン画面は「処理実行」と「編集ウィンドウ起動（ランチャー）」に寄せる。

Editor は 個別にテストしやすく、変更しやすい構成にする。

最終的なユーザー体験

メインGUIから以下を別ウィンドウで開ける：

Hospitals TOML editor（hospitals.toml）

Specified dates TOML editor（specified-dates.toml）

Workers TOML editor（workers.toml）※新規

Max assignments CSV editor（max-assignments.csv）※新規（または汎用CSV editor）

同一エディタを複数起動しない（起動済みなら前面へ）

1. リポジトリ構成（提案）

```
src/
  gui/
    app.py                 # 起動だけ
    main_window.py         # タブ + 編集ウィンドウ起動のハブ
    tabs/
      main_tab.py
      settings_tab.py      # “編集UIを持たず”ボタンでEditor起動
    editors/
      hospitals_editor.py  # 既存コード移植
      specified_editor.py  # 既存コード移植
      workers_editor.py    # 新規（同様のスタイル）
      csv_editor.py        # 新規（max-assignments向け）
    common/
      paths.py             # project rootと設定/データのパス集約
      window_registry.py   # editorの多重起動防止（参照保持＋前面表示）
tests/
  gui/
    test_window_registry.py
    test_settings_tab_launch.py
  editors/
    test_hospitals_editor_smoke.py
    test_specified_editor_smoke.py
    test_csv_editor_io.py
    test_workers_editor_io.py
```

2. 仕様（重要ポイント）
   2.1 Editor Window 共通仕様

各 Editor は QMainWindow として独立して動作する

以下の操作を提供：

Open（ファイルを開く）

Save（上書き保存）

Save As（名前をつけて保存）

.bak は作らない（omit）

変更検知（dirty）：

未保存変更がある状態で Open / New / Close を行う場合は確認ダイアログを出す

dirty 表示：タイトルに \* を付ける、またはステータスバーで表示（方式は自由）

2.2 起動（ランチャー）仕様

SettingsTab には編集機能を持たせず、ボタンで Editor を起動する

同一Editorは多重起動しない：

起動済みなら raise\_() / activateWindow() で前面へ

未起動なら生成して show()

起動時に “デフォルトパス” を渡して自動でそのファイルを開く（存在しなければOpenダイアログでもOK。できれば「ファイルがない時の新規作成」も各Editorに持たせる）

2.3 既存エディタの取り込み

Hospitals editor：提示されたコードを src/gui/editors/hospitals_editor.py に移植

main() は削除 or if **name** == "**main**" ブロックに隔離（アプリ本体からは import してウィンドウを生成）

可能なら open_path(Path) を public メソッドとして用意

Specified editor：同様に src/gui/editors/specified_editor.py に移植

open_path(Path) を用意

2.4 新規エディタ（workers / csv）

Workers TOML editor：Hospitals editor と同じ思想で AoT 編集

最低限：一覧（左）＋詳細（右）＋ Add/Edit/Delete ＋ Open/Save/Save As

TOML構造は既存の workers.toml 仕様に合わせる（既存ローダー load_workers が通る形）

初期段階は「主要フィールドのみ」でもOK（後から拡張）

CSV editor（max-assignments）：

最低限：表編集（QTableWidget）＋ Open/Save/Save As

保存時にCSVとして成立すること

型整形（整数）などは必要になってから。最初は文字列のままでもOK（ただし既存ローダーが壊れるなら整形を入れる）

3. 実装手順（Step-by-step / TDD前提）

以下は 各ステップ＝テスト追加 → 実装 → リファクタ → コミット の単位です。
Claude Code はこの順にやってください。

Step 1: Paths 集約（最小）
目的

PROJECT_ROOT や各種設定ファイルパスを一箇所に集約して、Editor起動時に使えるようにする

実装

src/gui/common/paths.py を追加

Paths dataclass を作る

例（仕様）：

project_root

config_dir, data_dir

hospitals_toml, workers_toml, specified_dates_toml, max_assignments_csv

テスト（pytest）

Paths.from_here(**file**) などで project_root が期待通りになること

各パスが project_root/... を指すこと

コミットメッセージ例

test: add Paths tests

feat: add gui Paths helper

Step 2: WindowRegistry（多重起動防止）
目的

エディタウィンドウを複数開かない仕組みを作る（参照保持）

実装

src/gui/common/window_registry.py

仕様：

get_or_create(key: str, factory: Callable[[], QMainWindow]) -> QMainWindow

起動済みなら同インスタンスを返す

返す際に前面へ（show() + raise\_() + activateWindow()）

テスト

factory が複数回呼ばれないこと

同じkeyで同一インスタンスが返ること
※ Qt を使うなら pytest-qt 推奨。難しければ “factory呼び出し回数” だけを単体テストで担保してOK。

コミット例

test: add WindowRegistry tests

feat: add WindowRegistry to prevent duplicate editors

Step 3: 既存エディタの移植（Hospitals / Specified）
目的

既存コードを src/gui/editors/ に取り込み、アプリから呼べる状態にする

実装

hospitals_editor.py / specified_editor.py を作成してコード移植

main() は残しても良いが、アプリからは使わない（呼び出しは MainWindow() を生成）

open_path(path: Path) を追加（既に load_toml() / open_file() があるのでそこに合わせて薄く追加）

テスト（smoke）

生成して show() できること（pytest-qt なら qtbot.addWidget 相当）

open_path に一時ファイルを渡して例外が出ないこと（最小）

コミット例

feat: move hospitals editor into gui/editors

feat: move specified editor into gui/editors

Step 4: SettingsTab を “ランチャー” に置換
目的

既存 SettingsTab の table/editor を削除し、ボタンで Editor を起動するだけにする

実装

src/gui/tabs/settings_tab.py を新規/更新

ボタン：

病院設定（hospitals editor起動）

病院別勤務希望日設定（specified editor起動）

勤務者設定（workers editor起動：未実装ならボタンだけでも）

勤務回数上限設定（csv editor起動：未実装ならボタンだけでも）

起動ロジックは WindowRegistry 経由

Paths を受け取る（MainWindowから注入）

テスト

各ボタン押下で registry に対応keyが登録され、factoryが呼ばれること

Editor本体はモックで良い（factory の呼び出しだけ確認）

コミット例

test: add settings launcher tests

refactor: convert SettingsTab to editor launcher

Step 5: MainWindow / app.py を薄く（依存注入）
目的

app.py は起動のみ、MainWindow が Paths と WindowRegistry を持つ

実装

src/gui/main_window.py を作り、tabs を貼る

tabs.addTab(SettingsTab(paths, registry), "設定") のように注入

src/gui/app.py は main() で起動するだけ

テスト

起動（MainWindow生成）が例外なくできる程度でOK

コミット例

refactor: extract MainWindow and thin app.py

Step 6: CSV Editor（max-assignments）
目的

最小のCSV編集ウィンドウを追加し、上限設定編集を別windowにする

実装（最小要件）

src/gui/editors/csv_editor.py

画面：

QTableWidget（セル編集可）

Open / Save / Save As

I/O：

open: csv読み込みして tableへ（pandasでも標準csvでもOK）

save: tableからcsvへ書き出し

.bak は作らない

テスト（優先）

table→csv→再読込で同じ行列が取れる（少数データでOK）

Save As で指定パスに保存できる（tmp_path）

コミット例

test: add csv editor IO tests

feat: add CSV editor for max-assignments

Step 7: Workers TOML Editor
目的

workers.toml も hospitals と同様に別windowで編集可能にする

実装（最小要件）

src/gui/editors/workers_editor.py

UI構成は hospitals editor を踏襲：

左：workers一覧

右：詳細フォーム（最低限 name など主要キー）

Add/Edit/Delete

Open / Save / Save As

TOML構造は既存の load_workers が読める形を維持（重要）

テスト

既存フォーマットの最小サンプルを tmp_path に作って open→save→parse が通る

load_workers があるなら、テストで実際に load_workers(saved_path) が成功するところまで確認できると強い

コミット例

test: add workers editor parse/roundtrip tests

feat: add workers.toml editor window

4. Git運用ルール（Claude Code向け）

1ステップにつき最低1コミット（できれば “test→feat” で2コミット）

コミット粒度の目安：

テスト追加（赤）→ 実装（緑）→ リファクタ（整理）

コミットメッセージは prefix をつける：

test: ...

feat: ...

refactor: ...

chore: ...

5. Done の定義（受け入れ基準）

設定タブ（SettingsTab）が “ランチャー” 化されている

Hospitals / Specified editor がアプリから起動できる

起動済みeditorは多重起動しない

各 editor に Open/Save/Save As がある

.bak は作らない

主要機能に対し最低限の自動テストがある（起動/IO/registry）

pytest が通る

lefthook pre-commit が通る（コード整形/静的解析）

6. Claude Code に伝える注意点（落とし穴回避）

Qt Window は参照が切れると閉じることがあるので、WindowRegistry で強参照保持すること

if **name** == "**main**": main() は editor モジュール内に残してもよいが、アプリ本体からの import 時に副作用が出ないようにする（トップレベルで QApplication() を作らない）

テストでQtを使う場合は pytest-qt があると楽。なければ “registryのfactory回数” や “I/O roundtrip” を中心に担保する

文字コードは一旦 utf-8 で統一（既存が utf-8-sig の場合は読み込み許容を広げてもよい）
