"""Pure logic tests for workers assignment helper functions."""

from __future__ import annotations

from pathlib import Path

from src.domain.types import ShiftType, Weekday, WorkerAssignmentRule
from src.gui.editors.workers_editor import (
    build_combo_choices,
    format_assignment_summary,
    load_hospital_choices,
)

SAMPLE_HOSPITALS_TOML = """\
[[hospitals]]
name = "病院A"
is_remote = false
is_university = false

[[hospitals]]
name = "病院B"
is_remote = true
is_university = false
"""


class TestLoadHospitalChoices:
    def test_returns_name_list(self, tmp_path: Path) -> None:
        f = tmp_path / "hospitals.toml"
        f.write_text(SAMPLE_HOSPITALS_TOML, encoding="utf-8")
        names = load_hospital_choices(f)
        assert names == ["病院A", "病院B"]

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.toml"
        names = load_hospital_choices(f)
        assert names == []

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.toml"
        f.write_text("", encoding="utf-8")
        names = load_hospital_choices(f)
        assert names == []


class TestBuildComboChoices:
    def test_known_hospital(self) -> None:
        known = ["病院A", "病院B"]
        result = build_combo_choices(known, "病院A")
        assert result == ["病院A", "病院B"]

    def test_unknown_hospital_prepended(self) -> None:
        known = ["病院A", "病院B"]
        result = build_combo_choices(known, "病院X")
        assert result == ["病院X", "病院A", "病院B"]

    def test_empty_current(self) -> None:
        known = ["病院A", "病院B"]
        result = build_combo_choices(known, "")
        assert result == ["病院A", "病院B"]

    def test_empty_known_with_current(self) -> None:
        result = build_combo_choices([], "病院X")
        assert result == ["病院X"]

    def test_both_empty(self) -> None:
        result = build_combo_choices([], "")
        assert result == []


class TestFormatAssignmentSummary:
    def test_full_assignment(self) -> None:
        a = WorkerAssignmentRule(
            hospital="病院A",
            weekdays=[Weekday.MONDAY, Weekday.TUESDAY],
            shift_type=ShiftType.DAY,
        )
        result = format_assignment_summary(a)
        assert result == "病院A / 日勤 / 月曜,火曜"

    def test_empty_weekdays(self) -> None:
        a = WorkerAssignmentRule(
            hospital="病院A",
            weekdays=[],
            shift_type=ShiftType.AM,
        )
        result = format_assignment_summary(a)
        assert result == "病院A / AM / "

    def test_single_weekday(self) -> None:
        a = WorkerAssignmentRule(
            hospital="病院B",
            weekdays=[Weekday.WEDNESDAY],
            shift_type=ShiftType.NIGHT,
        )
        result = format_assignment_summary(a)
        assert result == "病院B / 当直 / 水曜"
