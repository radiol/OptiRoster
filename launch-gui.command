#!/usr/bin/env bash
set -euo pipefail

# スクリプトのあるディレクトリ(=プロジェクト直下)へ移動
cd "$(dirname "$0")"

have() { command -v "$1" >/dev/null 2>&1; }

if ! have uv; then
  echo "[info] uv(python仮想環境構築ツール) が見つかりません。インストールを試みます…"
  if have brew; then brew install uv || true; fi
  if ! have uv; then
    if have curl; then curl -LsSf https://astral.sh/uv/install.sh | sh
    elif have wget; then wget -qO- https://astral.sh/uv/install.sh | sh
    else echo "[error] curl / wget がありません" >&2; exit 1; fi
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi

if ! have uv; then
  echo "[error] uv のインストールに失敗しました。" >&2
  exit 1
fi

# GUI 起動
exec uv run -m src.gui.app
