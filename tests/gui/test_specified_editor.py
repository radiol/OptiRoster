"""Tests for specified-dates editor conversion logic and IO.

Covers:
- HospitalEntry dataclass
- _ensure_hospitals (doc-level AoT helper)
- _entry_tbl_to_model (tomlkit table -> dataclass)
- _apply_model_to_entry_tbl (dataclass -> tomlkit table)
- load_specified_dates / dump_specified_dates (file-level IO)
- get_default_month (next-month calculation)
- is_in_displayed_month (cell visibility check)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import tomlkit

from src.gui.editors.specified_editor import (
    HospitalEntry,
    _apply_model_to_entry_tbl,
    _ensure_hospitals,
    _entry_tbl_to_model,
    dump_specified_dates,
    get_default_month,
    is_in_displayed_month,
    load_specified_dates,
)

SAMPLE_TOML = """\
[[hospitals]]
name = "病院5-治療"
dates = [2, 16, 30]

[[hospitals]]
name = "病院15"
dates = [2, 9, 16, 23, 30]
"""


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


# -- _entry_tbl_to_model -----------------------------------------------------
class TestEntryTblToModel:
    def test_basic_fields(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _entry_tbl_to_model(doc["hospitals"][0])
        assert isinstance(m, HospitalEntry)
        assert m.name == "病院5-治療"
        assert m.dates == {2, 16, 30}

    def test_multiple_dates(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        m = _entry_tbl_to_model(doc["hospitals"][1])
        assert m.name == "病院15"
        assert m.dates == {2, 9, 16, 23, 30}

    def test_no_dates_gives_empty_set(self):
        tbl = tomlkit.table()
        tbl["name"] = "NoDates"
        m = _entry_tbl_to_model(tbl)
        assert m.dates == set()


# -- _apply_model_to_entry_tbl -----------------------------------------------
class TestApplyModelToEntryTbl:
    def test_sets_basic_fields(self):
        tbl = tomlkit.table()
        model = HospitalEntry(name="X", dates={5, 10, 15})
        _apply_model_to_entry_tbl(tbl, model)
        assert str(tbl["name"]) == "X"
        assert list(tbl["dates"]) == [5, 10, 15]

    def test_replaces_existing_dates(self):
        doc = tomlkit.parse(SAMPLE_TOML)
        tbl = doc["hospitals"][0]
        model = HospitalEntry(name="病院5-治療", dates={1, 2, 3})
        _apply_model_to_entry_tbl(tbl, model)
        assert list(tbl["dates"]) == [1, 2, 3]

    def test_roundtrip_model(self):
        model = HospitalEntry(name="RT", dates={3, 7, 14, 21})
        tbl = tomlkit.table()
        _apply_model_to_entry_tbl(tbl, model)
        result = _entry_tbl_to_model(tbl)
        assert result.name == model.name
        assert result.dates == model.dates


# -- load / dump (file IO) ---------------------------------------------------
class TestLoadDump:
    def test_load_returns_hospital_entries(self, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        result = load_specified_dates(f)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], HospitalEntry)
        assert result[0].name == "病院5-治療"
        assert result[1].name == "病院15"

    def test_load_dates_detail(self, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        result = load_specified_dates(f)
        assert result[0].dates == {2, 16, 30}
        assert result[1].dates == {2, 9, 16, 23, 30}

    def test_dump_and_reload(self, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        model = load_specified_dates(f)
        out = tmp_path / "out.toml"
        dump_specified_dates(model, out)
        reloaded = load_specified_dates(out)
        assert len(reloaded) == len(model)
        for a, b in zip(model, reloaded, strict=True):
            assert a.name == b.name
            assert a.dates == b.dates

    def test_empty_file_loads_empty(self, tmp_path: Path):
        f = tmp_path / "empty.toml"
        f.write_text("", encoding="utf-8")
        assert load_specified_dates(f) == []

    def test_dump_produces_valid_toml(self, tmp_path: Path):
        f = tmp_path / "s.toml"
        f.write_text(SAMPLE_TOML, encoding="utf-8")
        model = load_specified_dates(f)
        out = tmp_path / "out.toml"
        dump_specified_dates(model, out)
        text = out.read_text(encoding="utf-8")
        parsed = tomlkit.parse(text)
        assert "hospitals" in parsed
        assert len(parsed["hospitals"]) == 2


# -- get_default_month -------------------------------------------------------
class TestGetDefaultMonth:
    def test_january_to_february(self):
        assert get_default_month(date(2026, 1, 31)) == (2026, 2)

    def test_mid_year(self):
        assert get_default_month(date(2026, 6, 15)) == (2026, 7)

    def test_december_to_next_year_january(self):
        assert get_default_month(date(2026, 12, 15)) == (2027, 1)

    def test_december_31(self):
        assert get_default_month(date(2026, 12, 31)) == (2027, 1)

    def test_february_to_march(self):
        assert get_default_month(date(2026, 2, 28)) == (2026, 3)


# -- is_in_displayed_month ---------------------------------------------------
class TestIsInDisplayedMonth:
    def test_same_month_returns_true(self):
        assert is_in_displayed_month(2026, 3, 2026, 3) is True

    def test_previous_month_returns_false(self):
        assert is_in_displayed_month(2026, 2, 2026, 3) is False

    def test_next_month_returns_false(self):
        assert is_in_displayed_month(2026, 4, 2026, 3) is False

    def test_different_year_returns_false(self):
        assert is_in_displayed_month(2025, 12, 2026, 1) is False
