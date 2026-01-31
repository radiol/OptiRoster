"""Tests for hospitals editor conversion logic and IO.

Covers:
- Constants (SHIFT_TYPES, WEEKDAYS, FREQUENCIES)
- _ensure_hospitals / _ensure_shifts (doc-level AoT helpers)
- _hosp_tbl_to_model (tomlkit table -> dataclass)
- _apply_model_to_hosp_tbl (dataclass -> tomlkit table)
- load_hospitals_toml / dump_hospitals_toml (file-level IO)
"""

from __future__ import annotations

from pathlib import Path

import tomlkit

from src.gui.editors.hospitals_editor import (
    FREQUENCIES,
    SHIFT_TYPES,
    WEEKDAYS,
    HospitalModel,
    ShiftModel,
    _apply_model_to_hosp_tbl,
    _ensure_hospitals,
    _hosp_tbl_to_model,
    dump_hospitals_toml,
    load_hospitals_toml,
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
    def test_shift_types_has_expected_values(self):
        for v in ("AM", "PM", "日勤", "当直"):
            assert v in SHIFT_TYPES

    def test_weekdays_has_seven(self):
        assert len(WEEKDAYS) == 7
        assert WEEKDAYS[0] == "月曜"
        assert WEEKDAYS[-1] == "日曜"

    def test_frequencies_has_expected_values(self):
        for v in ("毎週", "隔週", "指定日"):
            assert v in FREQUENCIES


# -- _ensure_hospitals -------------------------------------------------------
class TestEnsureHospitals:
    def test_adds_aot_to_empty_doc(self):
        doc = tomlkit.document()
        hosps = _ensure_hospitals(doc)
        assert "hospitals" in doc
        assert len(hosps) == 0

    def test_returns_existing_aot(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        hosps = _ensure_hospitals(doc)
        assert len(hosps) == 2

    def test_doc_without_hospitals_key(self):
        doc = tomlkit.parse("[other]\nfoo = 1\n")
        hosps = _ensure_hospitals(doc)
        assert "hospitals" in doc
        assert len(hosps) == 0


# -- _hosp_tbl_to_model -----------------------------------------------------
class TestHospTblToModel:
    def test_basic_fields(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _hosp_tbl_to_model(doc["hospitals"][0])
        assert isinstance(m, HospitalModel)
        assert m.name == "病院A"
        assert m.is_remote is False
        assert m.is_university is True

    def test_shifts_converted(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _hosp_tbl_to_model(doc["hospitals"][0])
        assert len(m.shifts) == 1
        s = m.shifts[0]
        assert isinstance(s, ShiftModel)
        assert s.shift_type == "当直"
        assert s.weekdays == ["月曜", "火曜"]
        assert s.frequency == "毎週"

    def test_multiple_shifts(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _hosp_tbl_to_model(doc["hospitals"][1])
        assert len(m.shifts) == 2
        assert m.shifts[0].shift_type == "日勤"
        assert m.shifts[1].shift_type == "AM"

    def test_no_shifts_gives_empty_list(self):
        tbl = tomlkit.table()
        tbl["name"] = "NoShift"
        tbl["is_remote"] = False
        tbl["is_university"] = False
        m = _hosp_tbl_to_model(tbl)
        assert m.shifts == []


# -- _apply_model_to_hosp_tbl -----------------------------------------------
class TestApplyModelToHospTbl:
    def test_sets_basic_fields(self):
        tbl = tomlkit.table()
        model = HospitalModel(
            name="X", is_remote=True, is_university=False, shifts=[]
        )
        _apply_model_to_hosp_tbl(tbl, model)
        assert str(tbl["name"]) == "X"
        assert bool(tbl["is_remote"]) is True
        assert bool(tbl["is_university"]) is False

    def test_sets_shifts(self):
        tbl = tomlkit.table()
        shift = ShiftModel(shift_type="AM", weekdays=["月曜"], frequency="毎週")
        model = HospitalModel(
            name="Y", is_remote=False, is_university=False, shifts=[shift]
        )
        _apply_model_to_hosp_tbl(tbl, model)
        assert "shifts" in tbl
        assert len(tbl["shifts"]) == 1
        assert str(tbl["shifts"][0]["shift_type"]) == "AM"

    def test_replaces_existing_shifts(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        tbl = doc["hospitals"][1]  # 病院B: 2 shifts
        new_shift = ShiftModel(shift_type="PM", weekdays=["金曜"], frequency="隔週")
        model = HospitalModel(
            name="病院B", is_remote=True, is_university=False, shifts=[new_shift]
        )
        _apply_model_to_hosp_tbl(tbl, model)
        assert len(tbl["shifts"]) == 1
        assert str(tbl["shifts"][0]["shift_type"]) == "PM"

    def test_roundtrip_model(self):
        shift = ShiftModel(
            shift_type="当直", weekdays=["月曜", "水曜"], frequency="毎週"
        )
        model = HospitalModel(
            name="RT", is_remote=True, is_university=True, shifts=[shift]
        )
        tbl = tomlkit.table()
        _apply_model_to_hosp_tbl(tbl, model)
        result = _hosp_tbl_to_model(tbl)
        assert result.name == model.name
        assert result.is_remote == model.is_remote
        assert result.is_university == model.is_university
        assert len(result.shifts) == 1
        assert result.shifts[0].shift_type == shift.shift_type
        assert result.shifts[0].weekdays == shift.weekdays
        assert result.shifts[0].frequency == shift.frequency


# -- load / dump (file IO) ---------------------------------------------------
class TestLoadDump:
    def test_load_returns_hospital_models(self, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        result = load_hospitals_toml(f)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], HospitalModel)
        assert result[0].name == "病院A"
        assert result[1].name == "病院B"

    def test_load_shifts_detail(self, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        result = load_hospitals_toml(f)
        assert len(result[0].shifts) == 1
        assert result[1].shifts[1].frequency == "隔週"

    def test_dump_and_reload(self, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        model = load_hospitals_toml(f)
        out = tmp_path / "out.toml"
        dump_hospitals_toml(model, out)
        reloaded = load_hospitals_toml(out)
        assert len(reloaded) == len(model)
        for a, b in zip(model, reloaded):
            assert a.name == b.name
            assert a.is_remote == b.is_remote
            assert a.is_university == b.is_university
            assert len(a.shifts) == len(b.shifts)

    def test_empty_file_loads_empty(self, tmp_path: Path):
        f = tmp_path / "empty.toml"
        f.write_text("", encoding="utf-8")
        assert load_hospitals_toml(f) == []

    def test_dump_produces_valid_toml(self, tmp_path: Path):
        f = tmp_path / "h.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        model = load_hospitals_toml(f)
        out = tmp_path / "out.toml"
        dump_hospitals_toml(model, out)
        text = out.read_text(encoding="utf-8")
        parsed = tomlkit.parse(text)
        assert "hospitals" in parsed
        assert len(parsed["hospitals"]) == 2
