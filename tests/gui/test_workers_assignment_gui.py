"""GUI tests for AssignmentDialog and WorkersEditorWindow assignment list."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.domain.types import ShiftType, Weekday, WorkerAssignmentRule
from src.gui.editors.workers_editor import AssignmentDialog, WorkersEditorWindow
from src.io.workers_loader import load_workers

SAMPLE_WORKERS_TOML = """\
[[workers]]
name = "診断01"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院1"
weekdays = ["月曜", "火曜"]
shift_type = "日勤"

[[workers]]
name = "診断02"
is_diagnostic_specialist = false
"""

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


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def editor(qapp):
    w = WorkersEditorWindow()
    yield w
    w.close()


class TestAssignmentDialog:
    def test_defaults(self, qapp) -> None:
        dlg = AssignmentDialog()
        a = dlg.get_assignment()
        assert a.hospital == ""
        assert a.weekdays == []
        assert isinstance(a.shift_type, ShiftType)
        dlg.close()

    def test_initial_values(self, qapp) -> None:
        initial = WorkerAssignmentRule(
            hospital="病院1",
            weekdays=[Weekday.MONDAY, Weekday.TUESDAY],
            shift_type=ShiftType.DAY,
        )
        dlg = AssignmentDialog(initial=initial)
        a = dlg.get_assignment()
        assert a.hospital == "病院1"
        assert a.weekdays == [Weekday.MONDAY, Weekday.TUESDAY]
        assert a.shift_type == ShiftType.DAY
        dlg.close()

    def test_with_hospital_choices(self, qapp) -> None:
        initial = WorkerAssignmentRule(
            hospital="病院A",
            weekdays=[Weekday.WEDNESDAY],
            shift_type=ShiftType.AM,
        )
        dlg = AssignmentDialog(initial=initial, hospital_choices=["病院A", "病院B"])
        assert dlg.combo_hospital.count() == 2
        assert dlg.combo_hospital.currentText() == "病院A"
        dlg.close()

    def test_unknown_hospital_in_choices(self, qapp) -> None:
        initial = WorkerAssignmentRule(
            hospital="病院X",
            weekdays=[Weekday.WEDNESDAY],
            shift_type=ShiftType.AM,
        )
        dlg = AssignmentDialog(initial=initial, hospital_choices=["病院A", "病院B"])
        # editable combo allows unknown hospitals
        assert dlg.combo_hospital.currentText() == "病院X"
        dlg.close()


class TestWorkersEditorAssignmentsList:
    def test_shows_assignments_in_list(self, editor, tmp_path: Path) -> None:
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(f)
        # Select first worker (has 1 assignment)
        editor._worker_list.setCurrentRow(0)
        assert editor._assignments_list.count() == 1

    def test_empty_assignments_list(self, editor, tmp_path: Path) -> None:
        f = tmp_path / "w.toml"
        f.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(f)
        # Select second worker (has 0 assignments)
        editor._worker_list.setCurrentRow(1)
        assert editor._assignments_list.count() == 0

    def test_set_hospitals_path(self, editor, tmp_path: Path) -> None:
        h = tmp_path / "hospitals.toml"
        h.write_text(SAMPLE_HOSPITALS_TOML, encoding="utf-8")
        editor.set_hospitals_path(h)
        assert editor._hospitals_path == h

    def test_save_roundtrip_with_gui(self, editor, tmp_path: Path) -> None:
        """Assignments survive open -> save roundtrip via GUI model."""
        src = tmp_path / "in.toml"
        src.write_text(SAMPLE_WORKERS_TOML, encoding="utf-8")
        editor.open_path(src)
        out = tmp_path / "out.toml"
        editor.save_to(out)
        reloaded = load_workers(str(out))
        assert len(reloaded[0].assignments) == 1
        a = reloaded[0].assignments[0]
        assert a.hospital == "病院1"
        assert a.weekdays[0].value == "月曜"
        assert a.shift_type.value == "日勤"
