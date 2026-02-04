"""Create missing config/data directories and default files on startup."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.gui.common.paths import Paths


def ensure_default_files(paths: Paths) -> list[Path]:
    """Create missing config/data directories and default files.

    Returns list of newly created file paths.
    Does NOT overwrite existing files.
    """
    from src.io.hospitals_writer import dump_hospitals
    from src.io.max_assignments_writer import dump_max_assignments_csv
    from src.io.specified_days_writer import dump_specified_days
    from src.io.workers_writer import dump_workers

    paths.config_dir.mkdir(parents=True, exist_ok=True)
    paths.data_dir.mkdir(parents=True, exist_ok=True)

    writers: list[tuple[Path, Callable[..., None], list[Any] | dict[Any, Any]]] = [
        (paths.hospitals_toml, dump_hospitals, []),
        (paths.workers_toml, dump_workers, []),
        (paths.specified_dates_toml, dump_specified_days, {}),
        (paths.max_assignments_csv, dump_max_assignments_csv, {}),
    ]

    created: list[Path] = []
    for file_path, writer_fn, empty_data in writers:
        if not file_path.exists():
            writer_fn(empty_data, str(file_path))
            created.append(file_path)

    return created
