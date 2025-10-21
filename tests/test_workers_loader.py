# tests/test_workers_loader.py
import textwrap

import pytest

from src.domain.types import ShiftType, Weekday, Worker, WorkerAssignmentRule
from src.io.workers_loader import load_workers


def write_toml(tmp_path, content: str):
    p = tmp_path / "workers.toml"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_load_basic_single_worker_with_assignments(tmp_path, capsys):
    toml = """
    [[workers]]
    name = "山田太郎"
    is_diagnostic_specialist = true

    [[workers.assignments]]
    hospital = "A病院"
    weekdays = ["月曜", "水曜", "金曜"]
    shift_type = "日勤"

    [[workers.assignments]]
    hospital = "B病院"
    weekdays = ["火曜"]
    shift_type = "当直"
    """
    path = write_toml(tmp_path, toml)

    workers = load_workers(str(path))
    _ = capsys.readouterr().out  # Capture output for testing

    assert isinstance(workers, list)
    assert len(workers) == 1
    w = workers[0]
    assert isinstance(w, Worker)
    assert w.name == "山田太郎"
    assert w.is_diagnostic_specialist is True

    assert len(w.assignments) == 2
    a0, a1 = w.assignments
    assert isinstance(a0, WorkerAssignmentRule)
    assert a0.hospital == "A病院"
    assert a0.weekdays == [Weekday.MONDAY, Weekday.WEDNESDAY, Weekday.FRIDAY]
    assert a0.shift_type == ShiftType.DAY

    assert a1.hospital == "B病院"
    assert a1.weekdays == [Weekday.TUESDAY]
    assert a1.shift_type == ShiftType.NIGHT

    # assert "Loaded config for worker: 山田太郎" in out


def test_worker_without_assignments_is_allowed(tmp_path):
    toml = """
    [[workers]]
    name = "佐藤花子"
    # assignments なし
    """
    path = write_toml(tmp_path, toml)
    workers = load_workers(str(path))

    assert len(workers) == 1
    w = workers[0]
    assert w.name == "佐藤花子"
    assert w.is_diagnostic_specialist is False  # 省略→False
    assert w.assignments == []


def test_multiple_workers_mixed_settings(tmp_path):
    toml = """
    [[workers]]
    name = "Aさん"
    is_diagnostic_specialist = true
    [[workers.assignments]]
    hospital = "X病院"
    weekdays = ["土曜"]
    shift_type = "当直"

    [[workers]]
    name = "Bさん"
    # assignments なし
    """
    path = write_toml(tmp_path, toml)
    workers = load_workers(str(path))

    assert [w.name for w in workers] == ["Aさん", "Bさん"]
    wa, wb = workers
    assert wa.is_diagnostic_specialist is True
    assert len(wa.assignments) == 1
    assert wa.assignments[0].weekdays == [Weekday.SATURDAY]
    assert wa.assignments[0].shift_type == ShiftType.NIGHT

    assert wb.is_diagnostic_specialist is False
    assert wb.assignments == []


def test_missing_workers_key_returns_empty_list(tmp_path):
    toml = """
    # workers 配列なし
    """
    path = write_toml(tmp_path, toml)
    workers = load_workers(str(path))
    assert workers == []


def test_missing_worker_name_raises(tmp_path):
    toml = """
    [[workers]]
    # name 欠落
    is_diagnostic_specialist = false
    """
    path = write_toml(tmp_path, toml)
    with pytest.raises(KeyError):
        load_workers(str(path))


def test_invalid_weekday_raises(tmp_path):
    toml = """
    [[workers]]
    name = "Cさん"
    [[workers.assignments]]
    hospital = "Z病院"
    weekdays = ["無効曜日"]   # Weekday に存在しない
    shift_type = "日勤"
    """
    path = write_toml(tmp_path, toml)
    with pytest.raises(ValueError):
        load_workers(str(path))


def test_invalid_shift_type_raises(tmp_path):
    toml = """
    [[workers]]
    name = "Dさん"
    [[workers.assignments]]
    hospital = "Y病院"
    weekdays = ["月曜"]
    shift_type = "無効シフト"
    """
    path = write_toml(tmp_path, toml)
    with pytest.raises(ValueError):
        load_workers(str(path))


@pytest.mark.parametrize(
    "hospital, weekdays, shift",
    [
        ("H1", ["月曜", "火曜"], "日勤"),
        ("H2", ["水曜"], "AM"),
        ("H3", ["木曜", "金曜"], "PM"),
        ("H4", ["土曜", "日曜"], "当直"),
    ],
)
def test_parametrized_assignments(tmp_path, hospital, weekdays, shift):
    weekdays_repr = "[" + ", ".join([f'"{d}"' for d in weekdays]) + "]"
    toml = f"""
    [[workers]]
    name = "Param太郎"

    [[workers.assignments]]
    hospital = "{hospital}"
    weekdays = {weekdays_repr}
    shift_type = "{shift}"
    """
    path = write_toml(tmp_path, toml)
    workers = load_workers(str(path))

    (w,) = workers
    (a,) = w.assignments
    assert a.hospital == hospital
    assert a.weekdays == [Weekday(d) for d in weekdays]
    assert a.shift_type == ShiftType(shift)
