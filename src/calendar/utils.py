from __future__ import annotations

import calendar
import datetime as dt

import jpholiday

from src.domain.types import Weekday

WEEKDAY_LIST = list(Weekday)


# 指定年・月の全日付を生成
def generate_monthly_dates(year: int, month: int) -> list[dt.date]:
    _, ndays = calendar.monthrange(year, month)
    return [dt.date(year, month, day) for day in range(1, ndays + 1)]


# 曜日判定
def is_weekday(d: dt.date, weekday: Weekday) -> bool:
    return WEEKDAY_LIST[d.weekday()] == weekday


# 週末判定(0=Mon ... 6=Sun)
def _is_weekend(d: dt.date) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun


def is_public_holiday(d: dt.date) -> bool:
    """平日の祝日かどうか(= 祝日 かつ 土日ではない)"""
    return jpholiday.is_holiday(d) and not _is_weekend(d)


def is_holiday_or_weekend(d: dt.date) -> bool:
    """土日祝いずれかに該当するか"""
    return _is_weekend(d) or jpholiday.is_holiday(d)


def is_last_holiday(d: dt.date) -> bool:
    """
    2日以上連続した『土日祝』の並びの最終日か?
    条件:
    - 当日が土日祝である
    - 前日も土日祝である(これで"2日以上"を保証)
    - 翌日が土日祝ではない(並びがここで終わる)
    """
    if not is_holiday_or_weekend(d):
        return False
    prev_day = d - dt.timedelta(days=1)
    next_day = d + dt.timedelta(days=1)
    return is_holiday_or_weekend(prev_day) and not is_holiday_or_weekend(next_day)
