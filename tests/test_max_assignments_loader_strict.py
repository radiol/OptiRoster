import textwrap

import pytest

from src.io.max_assignments_loader import load_max_assignments_csv


def test_valid_and_empty_values(tmp_path):
    csv_text = textwrap.dedent("""\
        Name,大学,病院A
        診断01,,
        診断02,2,1
        診断03,0,
    """)
    p = tmp_path / "ok.csv"
    p.write_text(csv_text, encoding="utf-8")

    got = load_max_assignments_csv(str(p))
    assert got[("診断01", "大学")] is None
    assert got[("診断02", "大学")] == 2
    assert got[("診断03", "大学")] == 0


def test_invalid_non_numeric_raises(tmp_path):
    csv_text = textwrap.dedent("""\
        Name,大学
        診断01,abc
    """)
    p = tmp_path / "bad.csv"
    p.write_text(csv_text, encoding="utf-8")

    with pytest.raises(ValueError) as e:
        load_max_assignments_csv(str(p))
    assert "abc" in str(e.value)


def test_invalid_negative_raises(tmp_path):
    csv_text = textwrap.dedent("""\
        Name,大学
        診断01,-1
    """)
    p = tmp_path / "bad2.csv"
    p.write_text(csv_text, encoding="utf-8")

    with pytest.raises(ValueError) as e:
        load_max_assignments_csv(str(p))
    assert "-1" in str(e.value)
