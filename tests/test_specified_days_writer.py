"""Tests for specified_days_writer -- write dict[str, list[int]] to TOML."""

from __future__ import annotations

from src.io.specified_days_loader import load_specified_days
from src.io.specified_days_writer import dump_specified_days


class TestDumpSpecifiedDaysBasic:
    def test_single_hospital(self, tmp_path) -> None:
        data = {"A病院": [1, 5, 12]}
        out = tmp_path / "specified_days.toml"
        dump_specified_days(data, str(out))

        text = out.read_text(encoding="utf-8")
        assert "A病院" in text
        assert "1" in text
        assert "12" in text

    def test_empty_dict_produces_valid_toml(self, tmp_path) -> None:
        out = tmp_path / "specified_days.toml"
        dump_specified_days({}, str(out))

        reloaded = load_specified_days(str(out))
        assert reloaded == {}

    def test_hospital_with_empty_dates(self, tmp_path) -> None:
        data = {"D病院": []}
        out = tmp_path / "specified_days.toml"
        dump_specified_days(data, str(out))

        reloaded = load_specified_days(str(out))
        assert reloaded == {"D病院": []}


class TestDumpLoadRoundTrip:
    def test_roundtrip_multiple_hospitals(self, tmp_path) -> None:
        original = {
            "A病院": [1, 5, 12],
            "B病院": [3, 20],
            "C病院": [],
        }
        out = tmp_path / "specified_days.toml"
        dump_specified_days(original, str(out))
        reloaded = load_specified_days(str(out))

        assert reloaded == original

    def test_roundtrip_preserves_day_order(self, tmp_path) -> None:
        original = {"X病院": [31, 15, 1, 28]}
        out = tmp_path / "specified_days.toml"
        dump_specified_days(original, str(out))
        reloaded = load_specified_days(str(out))

        assert reloaded["X病院"] == [31, 15, 1, 28]
