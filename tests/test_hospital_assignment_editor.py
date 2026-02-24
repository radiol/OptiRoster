"""Tests for HospitalAssignmentEditorWindow (Scenarios 1-8)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.gui.editors.hospital_assignment_editor import HospitalAssignmentEditorWindow

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WORKERS_TOML = """\
[[workers]]
name = "IVR01"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院2"
weekdays = ["金曜"]
shift_type = "日勤"

[[workers.assignments]]
hospital = "病院8"
weekdays = ["土曜"]
shift_type = "日勤"

[[workers]]
name = "IVR02"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院2"
weekdays = ["金曜"]
shift_type = "日勤"

[[workers]]
name = "診断01"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院1"
weekdays = ["月曜"]
shift_type = "当直"
"""

MAX_CSV_WITH_SETTINGS = """\
Name,病院1,病院2,病院8
IVR01,,1,
IVR02,,0,
診断01,,,
"""

MAX_CSV_ALL_DEFAULT = """\
Name,病院1,病院2,病院8
IVR01,,,
IVR02,,,
診断01,,,
"""


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def editor(qapp):
    w = HospitalAssignmentEditorWindow()
    yield w
    w.close()


@pytest.fixture()
def editor_with_workers(qapp, tmp_path: Path):
    workers_file = tmp_path / "workers.toml"
    workers_file.write_text(WORKERS_TOML, encoding="utf-8")
    w = HospitalAssignmentEditorWindow()
    w.set_workers_path(workers_file)
    yield w, tmp_path
    w.close()


# ---------------------------------------------------------------------------
# Scenario 1: 病院別に担当勤務者が表示される
# ---------------------------------------------------------------------------
class TestHospitalSectionsContainCorrectWorkers:
    def test_hospital_section_contains_assigned_worker(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        workers = editor.workers_for_hospital("病院2")
        assert "IVR01" in workers

    def test_multiple_workers_in_same_hospital(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        workers = editor.workers_for_hospital("病院2")
        assert "IVR01" in workers
        assert "IVR02" in workers


# ---------------------------------------------------------------------------
# Scenario 2: 担当でない病院に勤務者が表示されない
# ---------------------------------------------------------------------------
class TestWorkerNotInUnrelatedHospital:
    def test_ivr01_not_in_hospital1(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        workers = editor.workers_for_hospital("病院1")
        assert "IVR01" not in workers

    def test_hospital1_only_contains_diagnosed01(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        workers = editor.workers_for_hospital("病院1")
        assert workers == ["診断01"]


# ---------------------------------------------------------------------------
# Scenario 3: 現在の設定値が正しく選択状態になる
# ---------------------------------------------------------------------------
class TestCurrentValueReflected:
    def test_value_1_is_selected(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        assert editor.get_value("IVR01", "病院2") == 1

    def test_value_0_is_selected(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        assert editor.get_value("IVR02", "病院2") == 0

    def test_empty_value_is_none(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        assert editor.get_value("IVR01", "病院8") is None


# ---------------------------------------------------------------------------
# Scenario 4: ボタンクリックで設定値が変わる
# ---------------------------------------------------------------------------
class TestSetValue:
    def test_set_value_to_0(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        editor.set_value("IVR01", "病院2", 0)
        assert editor.get_value("IVR01", "病院2") == 0

    def test_set_value_to_none(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        editor.set_value("IVR01", "病院2", None)
        assert editor.get_value("IVR01", "病院2") is None

    def test_set_value_to_2(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        editor.set_value("IVR02", "病院2", 2)
        assert editor.get_value("IVR02", "病院2") == 2


# ---------------------------------------------------------------------------
# Scenario 5 & 6: has_non_default による強調判定
# ---------------------------------------------------------------------------
class TestHasNonDefault:
    def test_all_default_returns_false(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        assert editor.has_non_default("病院2") is False

    def test_with_zero_value_returns_true(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        # IVR02 の病院2 が 0 に設定されている
        assert editor.has_non_default("病院2") is True

    def test_set_value_then_non_default(self, editor_with_workers):
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        editor.set_value("IVR01", "病院2", 1)
        assert editor.has_non_default("病院2") is True


# ---------------------------------------------------------------------------
# Scenario 7: 保存すると max-assignments.csv 形式で書き出される
# ---------------------------------------------------------------------------
class TestSaveTo:
    def test_save_preserves_value(self, editor_with_workers, tmp_path: Path):
        editor, wt = editor_with_workers
        csv_file = wt / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)
        editor.set_value("IVR01", "病院2", 0)

        out = tmp_path / "out.csv"
        editor.save_to(out)

        from src.io.max_assignments_loader import load_max_assignments_csv

        data = load_max_assignments_csv(str(out))
        assert data[("IVR01", "病院2")] == 0

    def test_save_preserves_none_as_empty(self, editor_with_workers, tmp_path: Path):
        editor, wt = editor_with_workers
        csv_file = wt / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        out = tmp_path / "out.csv"
        editor.save_to(out)

        from src.io.max_assignments_loader import load_max_assignments_csv

        data = load_max_assignments_csv(str(out))
        assert data.get(("IVR01", "病院2")) is None

    def test_roundtrip_all_values(self, editor_with_workers, tmp_path: Path):
        editor, wt = editor_with_workers
        csv_file = wt / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        out = tmp_path / "out.csv"
        editor.save_to(out)

        from src.io.max_assignments_loader import load_max_assignments_csv

        data = load_max_assignments_csv(str(out))
        assert data[("IVR01", "病院2")] == 1
        assert data[("IVR02", "病院2")] == 0


# ---------------------------------------------------------------------------
# 折りたたみ動作
# ---------------------------------------------------------------------------
class TestCollapse:
    def test_all_default_hospital_is_collapsed(self, editor_with_workers):
        """全員無制限の病院は初期状態で折りたたまれている."""
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        # 病院2は全員無制限 -> 折りたたみ状態
        assert editor.is_collapsed("病院2") is True

    def test_non_default_hospital_is_expanded(self, editor_with_workers):
        """設定のある病院は初期状態で展開されている."""
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        # 病院2にIVR02=0の設定がある -> 展開状態
        assert editor.is_collapsed("病院2") is False

    def test_toggle_expands_collapsed_hospital(self, editor_with_workers):
        """折りたたまれた病院のヘッダをトグルすると展開される."""
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        editor.toggle_collapse("病院2")
        assert editor.is_collapsed("病院2") is False

    def test_toggle_collapses_expanded_hospital(self, editor_with_workers):
        """展開中の病院のヘッダをトグルすると折りたたまれる."""
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_WITH_SETTINGS, encoding="utf-8")
        editor.open_path(csv_file)

        editor.toggle_collapse("病院2")
        assert editor.is_collapsed("病院2") is True


# ---------------------------------------------------------------------------
# Scenario 8: workers.toml なしで開くと空のビューになる
# ---------------------------------------------------------------------------
class TestOpenWithoutWorkersPath:
    def test_open_without_workers_path_does_not_raise(self, editor, tmp_path: Path):
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        # set_workers_path を呼ばずに open_path を呼ぶ
        editor.open_path(csv_file)  # 例外が出ないこと
        assert editor.current_path == csv_file

    def test_open_without_workers_path_shows_empty(self, editor, tmp_path: Path):
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)
        assert editor.hospital_count() == 0


# ---------------------------------------------------------------------------
# workers.toml リロードボタン
# ---------------------------------------------------------------------------

WORKERS_TOML_UPDATED = """\
[[workers]]
name = "IVR01"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院8"
weekdays = ["土曜"]
shift_type = "日勤"

[[workers]]
name = "IVR02"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院2"
weekdays = ["金曜"]
shift_type = "日勤"

[[workers]]
name = "診断01"
is_diagnostic_specialist = true

[[workers.assignments]]
hospital = "病院1"
weekdays = ["月曜"]
shift_type = "当直"
"""


class TestReloadWorkersButton:
    def test_reload_button_exists(self, editor_with_workers):
        """ツールバーに Reload ボタンが存在する."""
        editor, _ = editor_with_workers
        assert hasattr(editor, "btn_reload")

    def test_reload_updates_hw_map(self, editor_with_workers):
        """Reload 後に workers.toml の変更が _hw_map に反映される."""
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        # 初期状態: IVR01 は 病院2 に所属
        assert "IVR01" in editor.workers_for_hospital("病院2")

        # workers.toml を更新 (IVR01 の 病院2 担当を削除)
        workers_toml = tmp_path / "workers.toml"
        workers_toml.write_text(WORKERS_TOML_UPDATED, encoding="utf-8")

        editor.btn_reload.click()

        assert "IVR01" not in editor.workers_for_hospital("病院2")

    def test_reload_preserves_model(self, editor_with_workers):
        """Reload しても編集中の max-assignments 設定値は保持される."""
        editor, tmp_path = editor_with_workers
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)

        editor.set_value("IVR02", "病院2", 1)

        workers_toml = tmp_path / "workers.toml"
        workers_toml.write_text(WORKERS_TOML_UPDATED, encoding="utf-8")

        editor.btn_reload.click()

        # IVR02 は WORKERS_TOML_UPDATED でも 病院2 に残るので値が保持される
        assert editor.get_value("IVR02", "病院2") == 1

    def test_reload_without_workers_path_does_not_raise(self, editor, tmp_path: Path):
        """workers.toml 未設定で Reload しても例外が出ない."""
        csv_file = tmp_path / "max.csv"
        csv_file.write_text(MAX_CSV_ALL_DEFAULT, encoding="utf-8")
        editor.open_path(csv_file)
        editor.btn_reload.click()  # 例外が出ないこと
