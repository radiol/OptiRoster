"""Unit tests for build_hospital_worker_map and build_worker_hospital_weekdays pure logic."""

from __future__ import annotations

from src.domain.types import ShiftType, Weekday, Worker, WorkerAssignmentRule
from src.gui.editors.hospital_assignment_editor import (
    build_hospital_worker_map,
    build_worker_hospital_weekdays,
)


def _rule(hospital: str) -> WorkerAssignmentRule:
    return WorkerAssignmentRule(
        hospital=hospital,
        weekdays=[Weekday.FRIDAY],
        shift_type=ShiftType.DAY,
    )


class TestBuildHospitalWorkerMap:
    def test_single_worker_single_hospital(self):
        workers = [Worker(name="IVR01", assignments=[_rule("病院2")])]
        result = build_hospital_worker_map(workers)
        assert "病院2" in result
        assert "IVR01" in result["病院2"]

    def test_worker_not_in_unrelated_hospital(self):
        workers = [Worker(name="IVR01", assignments=[_rule("病院2")])]
        result = build_hospital_worker_map(workers)
        assert "病院1" not in result

    def test_multiple_workers_same_hospital(self):
        workers = [
            Worker(name="IVR01", assignments=[_rule("病院2")]),
            Worker(name="IVR02", assignments=[_rule("病院2")]),
        ]
        result = build_hospital_worker_map(workers)
        assert set(result["病院2"]) == {"IVR01", "IVR02"}

    def test_worker_order_preserved(self):
        workers = [
            Worker(name="IVR01", assignments=[_rule("病院2")]),
            Worker(name="IVR02", assignments=[_rule("病院2")]),
            Worker(name="IVR03", assignments=[_rule("病院2")]),
        ]
        result = build_hospital_worker_map(workers)
        assert result["病院2"] == ["IVR01", "IVR02", "IVR03"]

    def test_worker_with_multiple_hospitals(self):
        workers = [Worker(name="IVR01", assignments=[_rule("病院2"), _rule("病院8")])]
        result = build_hospital_worker_map(workers)
        assert "IVR01" in result["病院2"]
        assert "IVR01" in result["病院8"]

    def test_duplicate_hospital_in_assignments_deduped(self):
        # 同じ病院が複数の曜日で登録されていても重複しない
        rule1 = WorkerAssignmentRule("病院2", [Weekday.FRIDAY], ShiftType.DAY)
        rule2 = WorkerAssignmentRule("病院2", [Weekday.TUESDAY], ShiftType.DAY)
        workers = [Worker(name="IVR01", assignments=[rule1, rule2])]
        result = build_hospital_worker_map(workers)
        assert result["病院2"].count("IVR01") == 1

    def test_worker_with_no_assignments(self):
        workers = [Worker(name="診断08", assignments=[])]
        result = build_hospital_worker_map(workers)
        # assignments がない勤務者はどの病院にも現れない
        for workers_list in result.values():
            assert "診断08" not in workers_list

    def test_empty_workers_returns_empty(self):
        result = build_hospital_worker_map([])
        assert result == {}


class TestBuildWorkerHospitalWeekdays:
    def test_single_rule_returns_short_weekday(self):
        # "金曜" -> "金"
        workers = [
            Worker(
                name="IVR01",
                assignments=[
                    WorkerAssignmentRule("病院2", [Weekday.FRIDAY], ShiftType.DAY),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("IVR01", "病院2")] == ["金"]

    def test_multiple_weekdays_in_one_rule(self):
        workers = [
            Worker(
                name="IVR01",
                assignments=[
                    WorkerAssignmentRule("病院2", [Weekday.MONDAY, Weekday.FRIDAY], ShiftType.DAY),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("IVR01", "病院2")] == ["月", "金"]

    def test_multiple_rules_same_hospital_merged(self):
        # 同一病院への複数ルール(曜日違い)はまとめる
        workers = [
            Worker(
                name="IVR01",
                assignments=[
                    WorkerAssignmentRule("病院2", [Weekday.MONDAY], ShiftType.DAY),
                    WorkerAssignmentRule("病院2", [Weekday.FRIDAY], ShiftType.DAY),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("IVR01", "病院2")] == ["月", "金"]

    def test_duplicate_weekday_deduped(self):
        # 同じ曜日が複数ルールに登場しても重複しない
        workers = [
            Worker(
                name="IVR01",
                assignments=[
                    WorkerAssignmentRule("病院2", [Weekday.FRIDAY], ShiftType.DAY),
                    WorkerAssignmentRule("病院2", [Weekday.FRIDAY], ShiftType.AM),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("IVR01", "病院2")].count("金") == 1

    def test_different_hospitals_independent(self):
        workers = [
            Worker(
                name="IVR01",
                assignments=[
                    WorkerAssignmentRule("病院2", [Weekday.FRIDAY], ShiftType.DAY),
                    WorkerAssignmentRule("病院8", [Weekday.SATURDAY], ShiftType.DAY),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("IVR01", "病院2")] == ["金"]
        assert result[("IVR01", "病院8")] == ["土"]

    def test_worker_with_no_assignments_returns_empty(self):
        workers = [Worker(name="診断08", assignments=[])]
        result = build_worker_hospital_weekdays(workers)
        assert result == {}

    def test_weekdays_sorted_in_canonical_order(self):
        # 日・月の順で登録しても 月・日 の順に正規化される
        workers = [
            Worker(
                name="IVR01",
                assignments=[
                    WorkerAssignmentRule(
                        "病院2", [Weekday.SUNDAY, Weekday.MONDAY], ShiftType.NIGHT
                    ),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("IVR01", "病院2")] == ["月", "日"]

    def test_weekdays_sorted_across_multiple_rules(self):
        # 複数ルールにまたがって追加された曜日も正規順にソートされる
        workers = [
            Worker(
                name="IVR01",
                assignments=[
                    WorkerAssignmentRule("病院2", [Weekday.FRIDAY], ShiftType.DAY),
                    WorkerAssignmentRule("病院2", [Weekday.MONDAY], ShiftType.DAY),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("IVR01", "病院2")] == ["月", "金"]

    def test_all_weekday_short_forms(self):
        weekdays = [
            Weekday.MONDAY,
            Weekday.TUESDAY,
            Weekday.WEDNESDAY,
            Weekday.THURSDAY,
            Weekday.FRIDAY,
            Weekday.SATURDAY,
            Weekday.SUNDAY,
        ]
        workers = [
            Worker(
                name="W",
                assignments=[
                    WorkerAssignmentRule("病院1", weekdays, ShiftType.NIGHT),
                ],
            )
        ]
        result = build_worker_hospital_weekdays(workers)
        assert result[("W", "病院1")] == ["月", "火", "水", "木", "金", "土", "日"]
