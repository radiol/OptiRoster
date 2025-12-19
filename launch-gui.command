#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

have() { command -v "$1" >/dev/null 2>&1; }

CI_MODE=0
if [[ "${1:-}" == "--ci" ]] || [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
  CI_MODE=1
fi

if ! have uv; then
  echo "[info] uv not found. trying to install..."

  if have brew; then
    brew install uv || true
  fi

  if ! have uv; then
    if have curl; then
      if [[ "$CI_MODE" == "1" ]]; then
        # CI: install to repo-local dir, do not touch profiles
        curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$PWD/.uv-bin" sh
        export PATH="$PWD/.uv-bin:$PATH"
      else
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
      fi
    elif have wget; then
      if [[ "$CI_MODE" == "1" ]]; then
        wget -qO- https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$PWD/.uv-bin" sh
        export PATH="$PWD/.uv-bin:$PATH"
      else
        wget -qO- https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
      fi
    else
      echo "[error] curl / wget がありません" >&2
      exit 1
    fi
  fi
fi

if ! have uv; then
  echo "[error] uv のインストールに失敗しました。" >&2
  exit 1
fi

if [[ "$CI_MODE" == "1" ]]; then
  uv --version
  uv run python -c "import src.gui.app; print('smoke: import ok')"
  exit 0
fi

exec uv run -m src.gui.app
