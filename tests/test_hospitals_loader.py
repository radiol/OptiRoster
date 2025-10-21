# tests/test_hospitals_loader.py
import textwrap

import pytest

from src.domain.types import Frequency, Hospital, HospitalDemandRule, ShiftType, Weekday
from src.io.hospitals_loader import load_hospitals


def write_toml(tmp_path, content: str):
    p = tmp_path / "hospitals.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_load_basic_single_hospital_weekly(tmp_path, capsys):
    # 日本語ラベルで定義(Enumと一致)
    toml = """
    [[hospitals]]
    name = "A病院"
    is_remote = true
    is_university = false

    [[hospitals.shifts]]
    shift_type = "日勤"
    weekdays = ["月曜", "水曜", "金曜"]
    frequency = "毎週"
    """
    path = write_toml(tmp_path, toml)

    hospitals = load_hospitals(str(path))
    _ = capsys.readouterr().out  # Capture output for testing

    assert isinstance(hospitals, list) and len(hospitals) == 1
    h = hospitals[0]
    assert isinstance(h, Hospital)
    assert h.name == "A病院"
    assert h.is_remote is True
    assert h.is_university is False

    assert len(h.demand_rules) == 1
    r = h.demand_rules[0]
    assert isinstance(r, HospitalDemandRule)
    assert r.shift_type == ShiftType.DAY
    assert r.weekdays == [Weekday.MONDAY, Weekday.WEDNESDAY, Weekday.FRIDAY]
    assert r.frequency == Frequency.WEEKLY

    # assert "Loaded config for hospital: A病院" in out


def test_default_frequency_is_weekly(tmp_path):
    toml = """
    [[hospitals]]
    name = "B病院"

    [[hospitals.shifts]]
    shift_type = "当直"
    weekdays = ["火曜", "木曜", "土曜"]
    # frequency 省略 → 毎週
    """
    path = write_toml(tmp_path, toml)
    hospitals = load_hospitals(str(path))
    r = hospitals[0].demand_rules[0]
    assert r.frequency == Frequency.WEEKLY


def test_empty_shifts_is_allowed(tmp_path):
    toml = """
    [[hospitals]]
    name = "C病院"
    # shifts なし
    """
    path = write_toml(tmp_path, toml)
    hospitals = load_hospitals(str(path))
    h = hospitals[0]
    assert h.name == "C病院"
    assert h.demand_rules == []


def test_flags_default_values(tmp_path):
    toml = """
    [[hospitals]]
    name = "D病院"
    # is_remote / is_university 省略 → False
    """
    path = write_toml(tmp_path, toml)
    h = load_hospitals(str(path))[0]
    assert h.is_remote is False
    assert h.is_university is False


def test_invalid_shift_type_raises(tmp_path):
    toml = """
    [[hospitals]]
    name = "E病院"

    [[hospitals.shifts]]
    shift_type = "無効なシフト"
    weekdays = ["月曜"]
    """
    path = write_toml(tmp_path, toml)
    with pytest.raises(ValueError):
        load_hospitals(str(path))


def test_missing_name_key_raises(tmp_path):
    toml = """
    [[hospitals]]
    # name 欠落
    is_remote = true
    """
    path = write_toml(tmp_path, toml)
    with pytest.raises(KeyError):
        load_hospitals(str(path))


@pytest.mark.parametrize(
    "shift_label, weekdays_labels, freq_label",
    [
        ("日勤", ["月曜", "火曜", "水曜"], "毎週"),
        ("当直", ["土曜", "日曜"], "隔週"),
        ("AM", ["水曜"], "毎週"),
        ("PM", [], "毎週"),
    ],
)
def test_parametrized_multiple_rules(tmp_path, shift_label, weekdays_labels, freq_label):
    freq_line = f'frequency = "{freq_label}"' if freq_label else ""
    toml = f"""
    [[hospitals]]
    name = "Param病院"

    [[hospitals.shifts]]
    shift_type = "{shift_label}"
    weekdays = {weekdays_labels}
    {freq_line}
    """
    path = write_toml(tmp_path, toml)
    hospitals = load_hospitals(str(path))

    h = hospitals[0]
    r = h.demand_rules[0]
    assert r.shift_type == ShiftType(shift_label)
    assert r.weekdays == [Weekday(w) for w in weekdays_labels]
    expected = freq_label or "毎週"
    assert r.frequency == Frequency(expected)
