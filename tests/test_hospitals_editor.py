"""Tests for hospitals editor conversion logic.

Covers:
- Constants (SHIFT_TYPES, WEEKDAYS, FREQUENCIES)
- _ensure_hospitals / _ensure_shifts (doc-level AoT helpers)
- _hosp_tbl_to_model (tomlkit table -> domain object)
- _apply_model_to_hosp_tbl (domain object -> tomlkit table)
"""

from __future__ import annotations

import tomlkit

from src.domain.types import (
    Frequency,
    Hospital,
    HospitalDemandRule,
    ShiftType,
    Weekday,
)
from src.gui.editors.hospitals_editor import (
    FREQUENCIES,
    SHIFT_TYPES,
    WEEKDAYS,
    _apply_model_to_hosp_tbl,
    _ensure_hospitals,
    _hosp_tbl_to_model,
)

SAMPLE_TOML = """\
[[hospitals]]
name = "病院A"
is_remote = false
is_university = true

[[hospitals.shifts]]
shift_type = "当直"
weekdays = ["月曜", "火曜"]
frequency = "毎週"

[[hospitals]]
name = "病院B"
is_remote = true
is_university = false

[[hospitals.shifts]]
shift_type = "日勤"
weekdays = ["水曜"]
frequency = "毎週"

[[hospitals.shifts]]
shift_type = "AM"
weekdays = ["木曜"]
frequency = "隔週"
"""


# -- Constants ---------------------------------------------------------------
class TestConstants:
    def test_shift_types_has_expected_values(self) -> None:
        for v in ("AM", "PM", "日勤", "当直"):
            assert v in SHIFT_TYPES

    def test_weekdays_has_seven(self) -> None:
        assert len(WEEKDAYS) == 7
        assert WEEKDAYS[0] == "月曜"
        assert WEEKDAYS[-1] == "日曜"

    def test_frequencies_has_expected_values(self) -> None:
        for v in ("毎週", "隔週", "指定日"):
            assert v in FREQUENCIES


# -- _ensure_hospitals -------------------------------------------------------
class TestEnsureHospitals:
    def test_adds_aot_to_empty_doc(self) -> None:
        doc = tomlkit.document()
        hosps = _ensure_hospitals(doc)
        assert "hospitals" in doc
        assert len(hosps) == 0

    def test_returns_existing_aot(self) -> None:
        doc = tomlkit.parse(SAMPLE_TOML)
        hosps = _ensure_hospitals(doc)
        assert len(hosps) == 2

    def test_doc_without_hospitals_key(self) -> None:
        doc = tomlkit.parse("[other]\nfoo = 1\n")
        hosps = _ensure_hospitals(doc)
        assert "hospitals" in doc
        assert len(hosps) == 0


# -- _hosp_tbl_to_model -----------------------------------------------------
class TestHospTblToModel:
    def test_basic_fields(self) -> None:
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _hosp_tbl_to_model(doc["hospitals"][0])
        assert isinstance(m, Hospital)
        assert m.name == "病院A"
        assert m.is_remote is False
        assert m.is_university is True

    def test_shifts_converted(self) -> None:
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _hosp_tbl_to_model(doc["hospitals"][0])
        assert len(m.demand_rules) == 1
        s = m.demand_rules[0]
        assert isinstance(s, HospitalDemandRule)
        assert s.shift_type == ShiftType.NIGHT
        assert s.weekdays == [Weekday.MONDAY, Weekday.TUESDAY]
        assert s.frequency == Frequency.WEEKLY

    def test_multiple_shifts(self) -> None:
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _hosp_tbl_to_model(doc["hospitals"][1])
        assert len(m.demand_rules) == 2
        assert m.demand_rules[0].shift_type == ShiftType.DAY
        assert m.demand_rules[1].shift_type == ShiftType.AM

    def test_no_shifts_gives_empty_list(self) -> None:
        tbl = tomlkit.table()
        tbl["name"] = "NoShift"
        tbl["is_remote"] = False
        tbl["is_university"] = False
        m = _hosp_tbl_to_model(tbl)
        assert m.demand_rules == []


# -- _apply_model_to_hosp_tbl -----------------------------------------------
class TestApplyModelToHospTbl:
    def test_sets_basic_fields(self) -> None:
        tbl = tomlkit.table()
        model = Hospital(name="X", is_remote=True, is_university=False, demand_rules=[])
        _apply_model_to_hosp_tbl(tbl, model)
        assert str(tbl["name"]) == "X"
        assert bool(tbl["is_remote"]) is True
        assert bool(tbl["is_university"]) is False

    def test_sets_shifts(self) -> None:
        tbl = tomlkit.table()
        rule = HospitalDemandRule(
            shift_type=ShiftType.AM,
            weekdays=[Weekday.MONDAY],
            frequency=Frequency.WEEKLY,
        )
        model = Hospital(name="Y", is_remote=False, is_university=False, demand_rules=[rule])
        _apply_model_to_hosp_tbl(tbl, model)
        assert "shifts" in tbl
        assert len(tbl["shifts"]) == 1
        assert str(tbl["shifts"][0]["shift_type"]) == "AM"

    def test_replaces_existing_shifts(self) -> None:
        doc = tomlkit.parse(SAMPLE_TOML)
        tbl = doc["hospitals"][1]  # 病院B: 2 shifts
        new_rule = HospitalDemandRule(
            shift_type=ShiftType.PM,
            weekdays=[Weekday.FRIDAY],
            frequency=Frequency.BIWEEKLY,
        )
        model = Hospital(name="病院B", is_remote=True, is_university=False, demand_rules=[new_rule])
        _apply_model_to_hosp_tbl(tbl, model)
        assert len(tbl["shifts"]) == 1
        assert str(tbl["shifts"][0]["shift_type"]) == "PM"

    def test_roundtrip_model(self) -> None:
        rule = HospitalDemandRule(
            shift_type=ShiftType.NIGHT,
            weekdays=[Weekday.MONDAY, Weekday.WEDNESDAY],
            frequency=Frequency.WEEKLY,
        )
        model = Hospital(name="RT", is_remote=True, is_university=True, demand_rules=[rule])
        tbl = tomlkit.table()
        _apply_model_to_hosp_tbl(tbl, model)
        result = _hosp_tbl_to_model(tbl)
        assert result.name == model.name
        assert result.is_remote == model.is_remote
        assert result.is_university == model.is_university
        assert len(result.demand_rules) == 1
        assert result.demand_rules[0].shift_type == rule.shift_type
        assert result.demand_rules[0].weekdays == rule.weekdays
        assert result.demand_rules[0].frequency == rule.frequency
