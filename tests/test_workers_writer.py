"""Tests for workers_writer -- write list[Worker] to TOML."""

from __future__ import annotations

from src.domain.types import ShiftType, Weekday, Worker, WorkerAssignmentRule
from src.io.workers_loader import load_workers
from src.io.workers_writer import dump_workers


class TestDumpWorkersBasic:
    def test_single_worker_with_assignment(self, tmp_path) -> None:
        workers = [
            Worker(
                name="山田太郎",
                is_diagnostic_specialist=True,
                assignments=[
                    WorkerAssignmentRule(
                        hospital="A病院",
                        weekdays=[Weekday.MONDAY, Weekday.WEDNESDAY],
                        shift_type=ShiftType.DAY,
                    ),
                ],
            ),
        ]
        out = tmp_path / "workers.toml"
        dump_workers(workers, str(out))

        text = out.read_text(encoding="utf-8")
        assert "山田太郎" in text
        assert "is_diagnostic_specialist = true" in text
        assert "A病院" in text
        assert "日勤" in text
        assert "月曜" in text

    def test_empty_list_produces_valid_toml(self, tmp_path) -> None:
        out = tmp_path / "workers.toml"
        dump_workers([], str(out))

        reloaded = load_workers(str(out))
        assert reloaded == []

    def test_worker_without_assignments(self, tmp_path) -> None:
        workers = [
            Worker(
                name="佐藤花子",
                is_diagnostic_specialist=False,
                assignments=[],
            ),
        ]
        out = tmp_path / "workers.toml"
        dump_workers(workers, str(out))

        reloaded = load_workers(str(out))
        assert len(reloaded) == 1
        assert reloaded[0].name == "佐藤花子"
        assert reloaded[0].is_diagnostic_specialist is False
        assert reloaded[0].assignments == []

    def test_specialist_flag_false(self, tmp_path) -> None:
        workers = [
            Worker(name="一般医", is_diagnostic_specialist=False, assignments=[]),
        ]
        out = tmp_path / "workers.toml"
        dump_workers(workers, str(out))

        text = out.read_text(encoding="utf-8")
        assert "is_diagnostic_specialist = false" in text


class TestDumpLoadRoundTrip:
    def test_roundtrip_preserves_all_fields(self, tmp_path) -> None:
        original = [
            Worker(
                name="John",
                is_diagnostic_specialist=True,
                assignments=[
                    WorkerAssignmentRule(
                        hospital="病院X",
                        weekdays=[
                            Weekday.MONDAY,
                            Weekday.TUESDAY,
                            Weekday.WEDNESDAY,
                            Weekday.THURSDAY,
                            Weekday.FRIDAY,
                            Weekday.SATURDAY,
                            Weekday.SUNDAY,
                        ],
                        shift_type=ShiftType.NIGHT,
                    ),
                    WorkerAssignmentRule(
                        hospital="病院Y",
                        weekdays=[Weekday.FRIDAY],
                        shift_type=ShiftType.DAY,
                    ),
                ],
            ),
            Worker(
                name="Jane",
                is_diagnostic_specialist=False,
                assignments=[],
            ),
        ]
        out = tmp_path / "workers.toml"
        dump_workers(original, str(out))
        reloaded = load_workers(str(out))

        assert len(reloaded) == len(original)
        for orig, rl in zip(original, reloaded, strict=True):
            assert orig.name == rl.name
            assert orig.is_diagnostic_specialist == rl.is_diagnostic_specialist
            assert len(orig.assignments) == len(rl.assignments)
            for o_a, r_a in zip(orig.assignments, rl.assignments, strict=True):
                assert o_a.hospital == r_a.hospital
                assert o_a.weekdays == r_a.weekdays
                assert o_a.shift_type == r_a.shift_type

    def test_roundtrip_all_shift_types(self, tmp_path) -> None:
        workers = [
            Worker(
                name="全シフト",
                is_diagnostic_specialist=False,
                assignments=[
                    WorkerAssignmentRule(
                        hospital="X病院",
                        weekdays=[Weekday.MONDAY],
                        shift_type=st,
                    )
                    for st in ShiftType
                ],
            ),
        ]
        out = tmp_path / "workers.toml"
        dump_workers(workers, str(out))
        reloaded = load_workers(str(out))

        assert len(reloaded[0].assignments) == len(ShiftType)
        for orig_a, rl_a in zip(workers[0].assignments, reloaded[0].assignments, strict=True):
            assert orig_a.shift_type == rl_a.shift_type

    def test_roundtrip_with_real_config(self, tmp_path) -> None:
        """Load the actual config, dump, reload and compare."""
        import os

        real_path = os.path.join("config", "workers.toml")
        if not os.path.exists(real_path):
            return  # skip if not available
        original = load_workers(real_path)
        out = tmp_path / "workers.toml"
        dump_workers(original, str(out))
        reloaded = load_workers(str(out))

        assert len(reloaded) == len(original)
        for orig, rl in zip(original, reloaded, strict=True):
            assert orig.name == rl.name
            assert orig.is_diagnostic_specialist == rl.is_diagnostic_specialist
            assert len(orig.assignments) == len(rl.assignments)
