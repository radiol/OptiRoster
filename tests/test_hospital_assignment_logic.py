"""Unit tests for build_hospital_worker_map pure logic."""

from __future__ import annotations

from src.domain.types import ShiftType, Weekday, Worker, WorkerAssignmentRule
from src.gui.editors.hospital_assignment_editor import build_hospital_worker_map


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
