"""往復テスト: specified editor のモデル⇔TOML変換ロジック."""

from pathlib import Path

import tomlkit

from src.gui.editors.specified_editor import (
    dump_specified_dates,
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


class TestSpecifiedDatesRoundTrip:
    """load → dump → load で同等のモデルが得られること."""

    def test_roundtrip_via_tmp_file(self, tmp_path: Path):
        src = tmp_path / "specified-dates.toml"
        src.write_text(SAMPLE_TOML, encoding="utf-8")

        model1 = load_specified_dates(src)
        dump_specified_dates(model1, src)
        model2 = load_specified_dates(src)

        assert model1 == model2

    def test_load_returns_dict(self, tmp_path: Path):
        src = tmp_path / "specified-dates.toml"
        src.write_text(SAMPLE_TOML, encoding="utf-8")

        model = load_specified_dates(src)
        assert isinstance(model, dict)
        assert model["病院5-治療"] == [2, 16, 30]
        assert model["病院15"] == [2, 9, 16, 23, 30]

    def test_dump_produces_valid_toml(self, tmp_path: Path):
        src = tmp_path / "specified-dates.toml"
        src.write_text(SAMPLE_TOML, encoding="utf-8")

        model = load_specified_dates(src)
        out = tmp_path / "out.toml"
        dump_specified_dates(model, out)

        text = out.read_text(encoding="utf-8")
        parsed = tomlkit.parse(text)
        assert "hospitals" in parsed

    def test_empty_file_loads_empty_dict(self, tmp_path: Path):
        src = tmp_path / "empty.toml"
        src.write_text("", encoding="utf-8")
        model = load_specified_dates(src)
        assert model == {}
