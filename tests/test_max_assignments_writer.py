"""Tests for max_assignments_writer -- write dict to CSV."""

from __future__ import annotations

from src.io.max_assignments_loader import load_max_assignments_csv
from src.io.max_assignments_writer import dump_max_assignments_csv


class TestDumpMaxAssignmentsBasic:
    def test_single_worker_single_hospital(self, tmp_path) -> None:
        data: dict[tuple[str, str], int | None] = {("診断01", "大学"): 2}
        out = tmp_path / "max.csv"
        dump_max_assignments_csv(data, str(out))

        text = out.read_text(encoding="utf-8")
        assert "Name,大学" in text
        assert "診断01,2" in text

    def test_none_written_as_empty(self, tmp_path) -> None:
        data: dict[tuple[str, str], int | None] = {("診断01", "大学"): None}
        out = tmp_path / "max.csv"
        dump_max_assignments_csv(data, str(out))

        text = out.read_text(encoding="utf-8")
        assert "診断01," in text
        # Should not contain "None"
        assert "None" not in text

    def test_zero_written_as_zero(self, tmp_path) -> None:
        data: dict[tuple[str, str], int | None] = {("診断01", "大学"): 0}
        out = tmp_path / "max.csv"
        dump_max_assignments_csv(data, str(out))

        text = out.read_text(encoding="utf-8")
        assert "診断01,0" in text

    def test_empty_dict_produces_header_only(self, tmp_path) -> None:
        data: dict[tuple[str, str], int | None] = {}
        out = tmp_path / "max.csv"
        dump_max_assignments_csv(data, str(out))

        text = out.read_text(encoding="utf-8")
        assert text.strip() == "Name"


class TestDumpLoadRoundTrip:
    def test_roundtrip_preserves_values(self, tmp_path) -> None:
        original: dict[tuple[str, str], int | None] = {
            ("診断01", "大学"): None,
            ("診断01", "病院A"): None,
            ("診断02", "大学"): 2,
            ("診断02", "病院A"): 1,
            ("診断03", "大学"): 0,
            ("診断03", "病院A"): None,
        }
        out = tmp_path / "max.csv"
        dump_max_assignments_csv(original, str(out))
        reloaded = load_max_assignments_csv(str(out))

        assert reloaded == original

    def test_roundtrip_many_hospitals(self, tmp_path) -> None:
        hospitals = ["H1", "H2", "H3", "H4", "H5"]
        original: dict[tuple[str, str], int | None] = {}
        for h in hospitals:
            original[("W1", h)] = None
            original[("W2", h)] = 1
        original[("W1", "H3")] = 3
        original[("W2", "H5")] = 0

        out = tmp_path / "max.csv"
        dump_max_assignments_csv(original, str(out))
        reloaded = load_max_assignments_csv(str(out))

        assert reloaded == original

    def test_roundtrip_with_real_csv(self, tmp_path) -> None:
        """Load the actual CSV, dump, reload and compare."""
        import os

        real_path = os.path.join("data", "max-assignments.csv")
        if not os.path.exists(real_path):
            return  # skip if not available
        original = load_max_assignments_csv(real_path)
        out = tmp_path / "max.csv"
        dump_max_assignments_csv(original, str(out))
        reloaded = load_max_assignments_csv(str(out))

        assert reloaded == original
