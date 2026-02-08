"""Tests for src.gui.common.ensure_config — ensure_default_files."""

from pathlib import Path

from src.gui.common.ensure_config import ensure_default_files
from src.gui.common.paths import Paths
from src.io.hospitals_loader import load_hospitals
from src.io.max_assignments_loader import load_max_assignments_csv
from src.io.specified_days_loader import load_specified_days
from src.io.workers_loader import load_workers


def _make_paths(tmp_path: Path) -> Paths:
    return Paths(project_root=tmp_path)


class TestEnsureDefaultFiles:
    """ensure_default_files creates missing dirs and files with valid defaults."""

    def test_creates_config_dir(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        ensure_default_files(paths)
        assert paths.config_dir.is_dir()

    def test_creates_data_dir(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        ensure_default_files(paths)
        assert paths.data_dir.is_dir()

    def test_creates_hospitals_toml(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        ensure_default_files(paths)
        assert paths.hospitals_toml.is_file()
        hospitals = load_hospitals(str(paths.hospitals_toml))
        assert hospitals == []

    def test_creates_workers_toml(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        ensure_default_files(paths)
        assert paths.workers_toml.is_file()
        workers = load_workers(str(paths.workers_toml))
        assert workers == []

    def test_creates_specified_dates_toml(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        ensure_default_files(paths)
        assert paths.specified_dates_toml.is_file()
        data = load_specified_days(str(paths.specified_dates_toml))
        assert data == {}

    def test_creates_max_assignments_csv(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        ensure_default_files(paths)
        assert paths.max_assignments_csv.is_file()
        data = load_max_assignments_csv(str(paths.max_assignments_csv))
        assert data == {}

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        paths.config_dir.mkdir(parents=True)
        sentinel = "# keep me\n"
        paths.hospitals_toml.write_text(sentinel, encoding="utf-8")

        ensure_default_files(paths)

        assert paths.hospitals_toml.read_text(encoding="utf-8") == sentinel

    def test_returns_created_paths(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        created = ensure_default_files(paths)
        assert set(created) == {
            paths.hospitals_toml,
            paths.workers_toml,
            paths.specified_dates_toml,
            paths.max_assignments_csv,
        }

    def test_all_exist_returns_empty(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        ensure_default_files(paths)  # create all
        created = ensure_default_files(paths)  # call again
        assert created == []
