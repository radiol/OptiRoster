# tests/test_holiday_utils.py
import datetime as dt
import itertools

import pytest

from src.calendar.utils import (
    generate_monthly_dates,
    is_holiday_or_weekend,
    is_last_holiday,
    is_public_holiday,
    is_weekday,
)
from src.domain.types import Weekday


def test_generate_monthly_dates_normal_month():
    days = generate_monthly_dates(2025, 10)  # 31日
    assert len(days) == 31
    assert days[0] == dt.date(2025, 10, 1)
    assert days[-1] == dt.date(2025, 10, 31)
    # 昇順かどうか
    assert all(a < b for a, b in itertools.pairwise(days))


def test_generate_monthly_dates_feb_non_leap():
    days = generate_monthly_dates(2025, 2)  # 平年の2月=28日
    assert len(days) == 28
    assert days[0] == dt.date(2025, 2, 1)
    assert days[-1] == dt.date(2025, 2, 28)


def test_generate_monthly_dates_feb_leap():
    days = generate_monthly_dates(2024, 2)  # うるう年
    assert len(days) == 29
    assert days[0] == dt.date(2024, 2, 1)
    assert days[-1] == dt.date(2024, 2, 29)


def test_generate_monthly_dates_december_edge():
    days = generate_monthly_dates(2025, 12)  # 月越えを使わないので安全
    assert len(days) == 31
    assert days[0] == dt.date(2025, 12, 1)
    assert days[-1] == dt.date(2025, 12, 31)


# ---------- 探索ヘルパ ----------


def _find_next_weekday(start: dt.date, weekday_int: int) -> dt.date:
    """start以降で weekday_int(0=Mon..6=Sun) の最初の日"""
    d = start
    while d.weekday() != weekday_int:
        d += dt.timedelta(days=1)
    return d


def _find_weekday_holiday(start_year: int, years: int = 4):
    """
    平日の祝日を1つ探す(見つからなければ None)。
    is_public_holiday を使って検出する。
    """
    start = dt.date(start_year, 1, 1)
    end = dt.date(start_year + years, 1, 1)
    d = start
    while d < end:
        if is_public_holiday(d):
            return d
        d += dt.timedelta(days=1)
    return None


def _find_consecutive_holidays_end(start_year: int, years: int = 4):
    """
    2日以上連続する『土日祝』の (先頭, 末尾) を返す。見つからない場合 None。
    """
    start = dt.date(start_year, 1, 1)
    end = dt.date(start_year + years, 1, 1)
    d = start
    while d < end:
        if is_holiday_or_weekend(d):
            run = [d]
            k = d + dt.timedelta(days=1)
            while k < end and is_holiday_or_weekend(k):
                run.append(k)
                k += dt.timedelta(days=1)
            if len(run) >= 2:
                return (run[0], run[-1])
            d = k
        else:
            d += dt.timedelta(days=1)
    return None


def _find_isolated_holiday_or_weekend(start_year: int, years: int = 3):
    """
    前後が平日で、当日だけが土日祝の単発日を探す。見つからない場合 None。
    """
    start = dt.date(start_year, 1, 1)
    end = dt.date(start_year + years, 1, 1)
    d = start
    while d < end:
        if is_holiday_or_weekend(d):
            prev_h = is_holiday_or_weekend(d - dt.timedelta(days=1))
            next_h = is_holiday_or_weekend(d + dt.timedelta(days=1))
            if not prev_h and not next_h:
                return d
        d += dt.timedelta(days=1)
    return None


# ---------- テスト ----------


def test_is_weekday_alignment_full_week():
    """
    is_weekday が Pythonの weekday() と Weekday Enum(日本語ラベル)の
    並びを正しく対応付けているか、連続7日で検証。
    """
    today = dt.date.today()
    start_mon = _find_next_weekday(today, 0)  # 次の月曜
    seq = [start_mon + dt.timedelta(days=i) for i in range(7)]
    expected = [
        Weekday.MONDAY,
        Weekday.TUESDAY,
        Weekday.WEDNESDAY,
        Weekday.THURSDAY,
        Weekday.FRIDAY,
        Weekday.SATURDAY,
        Weekday.SUNDAY,
    ]
    for d, exp in zip(seq, expected, strict=False):
        assert is_weekday(d, exp) is True
        # 隣の曜日は False になることを軽く確認
        assert is_weekday(d, expected[(d.weekday() + 1) % 7]) is False


def test_is_public_holiday_on_weekday_and_not_on_weekend():
    """
    平日の祝日は True、週末(土日)は False(定義どおり)を確認。
    """
    base_year = dt.date.today().year
    h = _find_weekday_holiday(base_year, years=4)
    if h is None:
        pytest.skip("平日の祝日が探索範囲で見つからずスキップ")
    assert h.weekday() < 5
    assert is_public_holiday(h) is True

    # 同じ週の土日(または直近の土日)が False であることを確認
    sat = h + dt.timedelta(days=(5 - h.weekday()))
    sun = sat + dt.timedelta(days=1)
    assert is_public_holiday(sat) is False
    assert is_public_holiday(sun) is False


def test_is_not_public_holiday():
    """
    節分の日(2026-02-03)や春分の日(2025-03-20)など、
    カレンダー上で表示されるが、休みではない日が祝日でないことを確認
    """
    non_holidays = [
        dt.date(2026, 2, 3),  # 節分の日
        dt.date(2026, 3, 3),  # ひな祭り
        dt.date(2026, 7, 7),  # 七夕
        dt.date(2026, 12, 25),  # クリスマス
    ]
    for d in non_holidays:
        assert is_public_holiday(d) is False


def test_is_last_holiday_on_consecutive_block():
    """
    2日以上連続する『土日祝』ブロックの最終日で True になる。
    先頭や中間は False。
    """
    base_year = dt.date.today().year
    block = _find_consecutive_holidays_end(base_year, years=4)
    if block is None:
        pytest.skip("2日以上連続する土日祝の並びが見つからずスキップ")
    first, last = block
    assert is_last_holiday(last) is True
    if first != last:
        assert is_last_holiday(first) is False
        mid = first + dt.timedelta(days=1)
        if mid < last:
            assert is_last_holiday(mid) is False


def test_is_last_holiday_singleton_is_false():
    """
    前後が平日で単発の土日祝は is_last_holiday=False。
    """
    base_year = dt.date.today().year
    d = _find_isolated_holiday_or_weekend(base_year, years=3)
    if d is None:
        pytest.skip("単発の土日祝が探索範囲で見つからずスキップ")
    assert is_last_holiday(d) is False


def test_is_year_end_holiday():
    """
    年末の12月28日~31日が祝日であることを確認。
    元々土日である場合は祝日ではない判定になることも確認。
    """
    year = 2025  # 例として2025年を使用
    dec_28 = dt.date(year, 12, 28)
    dec_29 = dt.date(year, 12, 29)
    dec_30 = dt.date(year, 12, 30)
    dec_31 = dt.date(year, 12, 31)
    assert is_holiday_or_weekend(dec_28) is True
    assert is_public_holiday(dec_28) is False  # 12/28は日曜日なので祝日ではない判定
    assert is_holiday_or_weekend(dec_29) is True
    assert is_public_holiday(dec_29) is True
    assert is_holiday_or_weekend(dec_30) is True
    assert is_public_holiday(dec_30) is True
    assert is_holiday_or_weekend(dec_31) is True
    assert is_public_holiday(dec_31) is True
    # 年末の12月26日は祝日ではないことを確認
    dec_26 = dt.date(year, 12, 26)
    assert is_holiday_or_weekend(dec_26) is False


def test_is_new_year_holiday():
    """
    年始の1月1日~3日が祝日であることを確認。
    元々土日である場合は祝日ではない判定になることも確認。
    """
    year = 2026  # 例として2026年を使用
    jan_1 = dt.date(year, 1, 1)
    jan_2 = dt.date(year, 1, 2)
    jan_3 = dt.date(year, 1, 3)
    assert is_holiday_or_weekend(jan_1) is True
    assert is_public_holiday(jan_1) is True
    assert is_holiday_or_weekend(jan_2) is True
    assert is_public_holiday(jan_2) is True
    assert is_holiday_or_weekend(jan_3) is True
    assert is_public_holiday(jan_3) is False  # 1月3日は土曜日なので祝日ではない判定

    # 年始の1月5日は祝日ではないことを確認
    jan_5 = dt.date(year, 1, 5)
    assert is_holiday_or_weekend(jan_5) is False
