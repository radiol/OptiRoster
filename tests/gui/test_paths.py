"""Tests for src.gui.common.paths — Paths dataclass."""

from pathlib import Path

from src.gui.common.paths import Paths


class TestPathsFromFile:
    """Paths.from_file() が project_root を正しく特定できること。"""

    def test_project_root_contains_pyproject(self):
        p = Paths.from_file(Path(__file__))
        assert (p.project_root / "pyproject.toml").exists()

    def test_config_dir(self):
        p = Paths.from_file(Path(__file__))
        assert p.config_dir == p.project_root / "config"

    def test_data_dir(self):
        p = Paths.from_file(Path(__file__))
        assert p.data_dir == p.project_root / "data"

    def test_hospitals_toml(self):
        p = Paths.from_file(Path(__file__))
        assert p.hospitals_toml == p.config_dir / "hospitals.toml"

    def test_workers_toml(self):
        p = Paths.from_file(Path(__file__))
        assert p.workers_toml == p.config_dir / "workers.toml"

    def test_specified_dates_toml(self):
        p = Paths.from_file(Path(__file__))
        assert p.specified_dates_toml == p.data_dir / "specified-dates.toml"

    def test_max_assignments_csv(self):
        p = Paths.from_file(Path(__file__))
        assert p.max_assignments_csv == p.data_dir / "max-assignments.csv"


class TestPathsAllArePathInstances:
    def test_all_fields_are_path(self):
        p = Paths.from_file(Path(__file__))
        for name in (
            "project_root",
            "config_dir",
            "data_dir",
            "hospitals_toml",
            "workers_toml",
            "specified_dates_toml",
            "max_assignments_csv",
        ):
            assert isinstance(getattr(p, name), Path), f"{name} is not a Path"


class TestPathsFromExplicitRoot:
    """明示的な project_root を渡すケース。"""

    def test_explicit_root(self, tmp_path: Path):
        p = Paths(project_root=tmp_path)
        assert p.config_dir == tmp_path / "config"
        assert p.data_dir == tmp_path / "data"
        assert p.hospitals_toml == tmp_path / "config" / "hospitals.toml"
