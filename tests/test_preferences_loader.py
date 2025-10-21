# tests/test_preferences_loader_csv.py
import datetime as dt
import textwrap

from src.io.preferences_loader import PreferenceStatus, load_preferences_csv


def test_csv_with_garbage_columns_is_ignored(tmp_path):
    # A:ID(不要) , B:氏名(必要), C:備考(不要), D/E:日付列(必要)
    csv_text = textwrap.dedent("""\
        ID,氏名,備考,2025年10月 勤務希望 [10/1(水)],2025年10月 勤務希望 [10/2(木)]
        1,診断02,メモ,当直不可,当直不可
        2,診断03,,,
    """)
    p = tmp_path / "prefs.csv"
    p.write_text(csv_text, encoding="utf-8")

    got = load_preferences_csv(str(p))
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)

    assert got[("診断02", d1)] == PreferenceStatus.NIGHT_FORBIDDEN
    assert got[("診断02", d2)] == PreferenceStatus.NIGHT_FORBIDDEN
    assert got[("診断03", d1)] == PreferenceStatus.NONE
    assert got[("診断03", d2)] == PreferenceStatus.NONE
