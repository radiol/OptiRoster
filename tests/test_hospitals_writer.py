"""Tests for hospitals_writer -- write list[Hospital] to TOML."""

from __future__ import annotations

from src.domain.types import Frequency, Hospital, HospitalDemandRule, ShiftType, Weekday
from src.io.hospitals_loader import load_hospitals
from src.io.hospitals_writer import dump_hospitals


class TestDumpHospitalsBasic:
    def test_single_hospital_with_shift(self, tmp_path) -> None:
        hospitals = [
            Hospital(
                name="A病院",
                is_remote=True,
                is_university=False,
                demand_rules=[
                    HospitalDemandRule(
                        shift_type=ShiftType.DAY,
                        weekdays=[Weekday.MONDAY, Weekday.WEDNESDAY],
                        frequency=Frequency.WEEKLY,
                    ),
                ],
            ),
        ]
        out = tmp_path / "hospitals.toml"
        dump_hospitals(hospitals, str(out))

        text = out.read_text(encoding="utf-8")
        assert "A病院" in text
        assert "is_remote = true" in text
        assert "is_university = false" in text
        assert "日勤" in text
        assert "月曜" in text

    def test_empty_list_produces_valid_toml(self, tmp_path) -> None:
        out = tmp_path / "hospitals.toml"
        dump_hospitals([], str(out))

        reloaded = load_hospitals(str(out))
        assert reloaded == []

    def test_hospital_without_shifts(self, tmp_path) -> None:
        hospitals = [
            Hospital(
                name="空病院",
                is_remote=False,
                is_university=True,
                demand_rules=[],
            ),
        ]
        out = tmp_path / "hospitals.toml"
        dump_hospitals(hospitals, str(out))

        reloaded = load_hospitals(str(out))
        assert len(reloaded) == 1
        assert reloaded[0].name == "空病院"
        assert reloaded[0].is_university is True
        assert reloaded[0].demand_rules == []


class TestDumpLoadRoundTrip:
    def test_roundtrip_preserves_all_fields(self, tmp_path) -> None:
        original = [
            Hospital(
                name="大学",
                is_remote=False,
                is_university=True,
                demand_rules=[
                    HospitalDemandRule(
                        shift_type=ShiftType.NIGHT,
                        weekdays=[
                            Weekday.MONDAY,
                            Weekday.TUESDAY,
                            Weekday.WEDNESDAY,
                            Weekday.THURSDAY,
                            Weekday.FRIDAY,
                            Weekday.SATURDAY,
                            Weekday.SUNDAY,
                        ],
                        frequency=Frequency.WEEKLY,
                    ),
                ],
            ),
            Hospital(
                name="鳥日赤",
                is_remote=True,
                is_university=False,
                demand_rules=[
                    HospitalDemandRule(
                        shift_type=ShiftType.DAY,
                        weekdays=[Weekday.TUESDAY, Weekday.WEDNESDAY, Weekday.FRIDAY],
                        frequency=Frequency.WEEKLY,
                    ),
                    HospitalDemandRule(
                        shift_type=ShiftType.AM,
                        weekdays=[Weekday.THURSDAY],
                        frequency=Frequency.BIWEEKLY,
                    ),
                ],
            ),
        ]
        out = tmp_path / "hospitals.toml"
        dump_hospitals(original, str(out))
        reloaded = load_hospitals(str(out))

        assert len(reloaded) == len(original)
        for orig, rl in zip(original, reloaded, strict=True):
            assert orig.name == rl.name
            assert orig.is_remote == rl.is_remote
            assert orig.is_university == rl.is_university
            assert len(orig.demand_rules) == len(rl.demand_rules)
            for o_rule, r_rule in zip(orig.demand_rules, rl.demand_rules, strict=True):
                assert o_rule.shift_type == r_rule.shift_type
                assert o_rule.weekdays == r_rule.weekdays
                assert o_rule.frequency == r_rule.frequency

    def test_roundtrip_all_shift_types(self, tmp_path) -> None:
        hospitals = [
            Hospital(
                name="全シフト病院",
                is_remote=False,
                is_university=False,
                demand_rules=[
                    HospitalDemandRule(
                        shift_type=st,
                        weekdays=[Weekday.MONDAY],
                        frequency=Frequency.WEEKLY,
                    )
                    for st in ShiftType
                ],
            ),
        ]
        out = tmp_path / "hospitals.toml"
        dump_hospitals(hospitals, str(out))
        reloaded = load_hospitals(str(out))

        assert len(reloaded[0].demand_rules) == len(ShiftType)
        for orig_rule, rl_rule in zip(
            hospitals[0].demand_rules, reloaded[0].demand_rules, strict=True
        ):
            assert orig_rule.shift_type == rl_rule.shift_type

    def test_roundtrip_all_frequencies(self, tmp_path) -> None:
        hospitals = [
            Hospital(
                name="全頻度病院",
                is_remote=False,
                is_university=False,
                demand_rules=[
                    HospitalDemandRule(
                        shift_type=ShiftType.DAY,
                        weekdays=[Weekday.MONDAY],
                        frequency=freq,
                    )
                    for freq in Frequency
                ],
            ),
        ]
        out = tmp_path / "hospitals.toml"
        dump_hospitals(hospitals, str(out))
        reloaded = load_hospitals(str(out))

        for orig_rule, rl_rule in zip(
            hospitals[0].demand_rules, reloaded[0].demand_rules, strict=True
        ):
            assert orig_rule.frequency == rl_rule.frequency

    def test_roundtrip_with_real_config(self, tmp_path) -> None:
        """Load the actual config, dump, reload and compare."""
        import os

        real_path = os.path.join("config", "hospitals.toml")
        if not os.path.exists(real_path):
            return  # skip if not available
        original = load_hospitals(real_path)
        out = tmp_path / "hospitals.toml"
        dump_hospitals(original, str(out))
        reloaded = load_hospitals(str(out))

        assert len(reloaded) == len(original)
        for orig, rl in zip(original, reloaded, strict=True):
            assert orig.name == rl.name
            assert orig.is_remote == rl.is_remote
            assert orig.is_university == rl.is_university
            assert len(orig.demand_rules) == len(rl.demand_rules)
