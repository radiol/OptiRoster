import datetime as dt
import textwrap

from src.io.preferences_loader import (
    PreferenceStatus,
    load_preferences_csv,
)


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return p


def test_blank_becomes_night_forbidden_if_any_wants_night(tmp_path):
    """
    同一勤務者に『当直希望』が1つでもある場合、空欄セルは当直不可として読む。
    """
    csv_path = _write(
        tmp_path,
        "prefs.csv",
        """
        氏名,2025年10月 勤務希望 [10/1(水)],2025年10月 勤務希望 [10/2(木)], 2025年10月 勤務希望 [10/3(金)]
        診断01,当直希望, ,
        診断02, , , 
        """,  # noqa: E501
    )
    res = load_preferences_csv(str(csv_path))
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)
    d3 = dt.date(2025, 10, 3)

    # 診断01: どこかに『当直希望』がある → 空欄は当直不可に解釈
    assert res[("診断01", d2)] == PreferenceStatus.NIGHT_FORBIDDEN
    assert res[("診断01", d3)] == PreferenceStatus.NIGHT_FORBIDDEN
    # 『当直希望』セル自体は制限ではない(NONE)
    assert res[("診断01", d1)] == PreferenceStatus.NONE

    # 診断02: 『当直希望』なし → 空欄は制限なしのまま
    assert res[("診断02", d1)] == PreferenceStatus.NONE
    assert res[("診断02", d2)] == PreferenceStatus.NONE
    assert res[("診断02", d3)] == PreferenceStatus.NONE


def test_explicit_forbids_take_precedence(tmp_path):
    """
    明示の『当直不可』『日勤・当直不可』は空欄ルールより優先される。
    """
    csv_path = _write(
        tmp_path,
        "prefs.csv",
        """
        氏名,2025年10月 勤務希望 [10/1(水)],2025年10月 勤務希望 [10/2(木)], 2025年10月 勤務希望 [10/3(金)]
        診断01,当直希望,当直不可,日勤・当直不可
        """,  # noqa: E501
    )
    res = load_preferences_csv(str(csv_path))
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)
    d3 = dt.date(2025, 10, 3)

    assert res[("診断01", d1)] == PreferenceStatus.NONE  # 当直希望セルは制限ではない
    assert res[("診断01", d2)] == PreferenceStatus.NIGHT_FORBIDDEN
    assert res[("診断01", d3)] == PreferenceStatus.DAY_NIGHT_FORBIDDEN


def test_garbage_columns_are_ignored(tmp_path):
    """
    A/C列など不要データが混ざっても、『氏名』と日付ヘッダ列だけを採用できる。
    """
    csv_path = _write(
        tmp_path,
        "prefs.csv",
        """
        氏名,ごみ列A,2025年10月 勤務希望 [10/1(水)],ごみ列C,2025年10月 勤務希望 [10/2(木)]
        診断02,XYZ,当直希望,ABC,
        """,
    )
    res = load_preferences_csv(str(csv_path))
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)

    # d1 は『当直希望』→ NONE(制限ではない)
    assert res[("診断02", d1)] == PreferenceStatus.NONE
    # 『当直希望』が1つでもあるので、空欄(d2)は当直不可へ
    assert res[("診断02", d2)] == PreferenceStatus.NIGHT_FORBIDDEN


def test_bom_and_spaces_handled(tmp_path):
    """
    UTF-8 BOM や空白混じりのセルも正しく解釈できる。
    """
    content = (
        "\ufeff"
        + textwrap.dedent(
            """
        氏名,2025年10月 勤務希望 [10/1(水)],2025年10月 勤務希望 [10/2(木)]
        診断03, 当直希望 ,
        """
        ).strip()
    )
    p = tmp_path / "prefs_bom.csv"
    p.write_text(content, encoding="utf-8")

    res = load_preferences_csv(str(p))
    d1 = dt.date(2025, 10, 1)
    d2 = dt.date(2025, 10, 2)

    # トリムされて『当直希望』判定される
    assert res[("診断03", d1)] == PreferenceStatus.NONE
    # 空欄は当直不可(当直希望があるため)
    assert res[("診断03", d2)] == PreferenceStatus.NIGHT_FORBIDDEN
