"""GUI用パス集約モジュール。

プロジェクトルートと各設定/データファイルのパスを一箇所で管理する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _find_project_root(start: Path) -> Path:
    """pyproject.toml を含む最も近い祖先ディレクトリを返す。"""
    current = start if start.is_dir() else start.parent
    for ancestor in (current, *current.parents):
        if (ancestor / "pyproject.toml").exists():
            return ancestor
    msg = f"pyproject.toml not found above {start}"
    raise FileNotFoundError(msg)


@dataclass(frozen=True)
class Paths:
    """プロジェクト内の主要パスを集約する dataclass。"""

    project_root: Path

    # --- derived (post_init) ---
    config_dir: Path = field(init=False)
    data_dir: Path = field(init=False)
    hospitals_toml: Path = field(init=False)
    workers_toml: Path = field(init=False)
    specified_dates_toml: Path = field(init=False)
    max_assignments_csv: Path = field(init=False)

    def __post_init__(self) -> None:
        root = self.project_root
        object.__setattr__(self, "config_dir", root / "config")
        object.__setattr__(self, "data_dir", root / "data")
        object.__setattr__(self, "hospitals_toml", root / "config" / "hospitals.toml")
        object.__setattr__(self, "workers_toml", root / "config" / "workers.toml")
        object.__setattr__(self, "specified_dates_toml", root / "data" / "specified-dates.toml")
        object.__setattr__(self, "max_assignments_csv", root / "data" / "max-assignments.csv")

    @classmethod
    def from_file(cls, file: str | Path) -> Paths:
        """任意のプロジェクト内ファイルからルートを特定して生成する。"""
        return cls(project_root=_find_project_root(Path(file).resolve()))
