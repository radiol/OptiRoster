"""往復テスト: hospitals editor のモデル⇔TOML変換ロジック."""

from pathlib import Path

import tomlkit

from src.gui.editors.hospitals_editor import (
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


class TestHospitalsRoundTrip:
    """load → dump → load で同等のモデルが得られること."""

    def test_roundtrip_via_tmp_file(self, tmp_path: Path):
        src = tmp_path / "hospitals.toml"
        src.write_text(SAMPLE_TOML, encoding="utf-8")

        model1 = load_hospitals_toml(src)
        dump_hospitals_toml(model1, src)
        model2 = load_hospitals_toml(src)

        assert len(model1) == len(model2)
        for a, b in zip(model1, model2):
            assert a["name"] == b["name"]
            assert a["is_remote"] == b["is_remote"]
            assert a["is_university"] == b["is_university"]
            assert len(a["shifts"]) == len(b["shifts"])
            for sa, sb in zip(a["shifts"], b["shifts"]):
                assert sa["shift_type"] == sb["shift_type"]
                assert list(sa["weekdays"]) == list(sb["weekdays"])
                assert sa["frequency"] == sb["frequency"]

    def test_load_returns_list_of_dicts(self, tmp_path: Path):
        src = tmp_path / "hospitals.toml"
        src.write_text(SAMPLE_TOML, encoding="utf-8")

        model = load_hospitals_toml(src)
        assert isinstance(model, list)
        assert len(model) == 2
        assert model[0]["name"] == "病院A"
        assert model[1]["name"] == "病院B"
        assert model[1]["shifts"][1]["frequency"] == "隔週"

    def test_dump_produces_valid_toml(self, tmp_path: Path):
        src = tmp_path / "hospitals.toml"
        src.write_text(SAMPLE_TOML, encoding="utf-8")

        model = load_hospitals_toml(src)
        out = tmp_path / "out.toml"
        dump_hospitals_toml(model, out)

        text = out.read_text(encoding="utf-8")
        parsed = tomlkit.parse(text)
        assert "hospitals" in parsed

    def test_empty_file_loads_empty_list(self, tmp_path: Path):
        src = tmp_path / "empty.toml"
        src.write_text("", encoding="utf-8")
        model = load_hospitals_toml(src)
        assert model == []
