from __future__ import annotations

from datetime import date

from src.calendar.utils import is_public_holiday
from src.domain.types import Frequency, Hospital, ShiftType, Weekday


def compute_required_map(
    hospitals: list[Hospital],
    days: list[date],
    weekdays: list[Weekday],
    specified_days: dict[str, list[int]],
) -> dict[tuple[str, date], set[ShiftType]]:
    """
    (病院h, 日d) に “必要なシフト種別の集合” を返す。
    例: {("大学", 2025-10-09): {ShiftType.NIGHT}, ...}
    """
    required: dict[tuple[str, date], set[ShiftType]] = {}
    for h in hospitals:
        # 各日ごとの必要シフト集合
        daily: list[set[ShiftType]] = [set() for _ in days]
        for rule in h.demand_rules:
            s = rule.shift_type
            match rule.frequency:
                case Frequency.WEEKLY:
                    for i, d in enumerate(days):
                        if is_public_holiday(d) and s != ShiftType.NIGHT:
                            continue
                        if weekdays[d.weekday()] in rule.weekdays:
                            daily[i].add(s)
                case Frequency.BIWEEKLY:
                    biweekly_cnt = 0
                    for i, d in enumerate(days):
                        if biweekly_cnt >= 2:
                            break
                        if is_public_holiday(d) and s != ShiftType.NIGHT:
                            continue
                        if i >= 7 and (s in daily[i - 7]):
                            continue
                        if weekdays[d.weekday()] in rule.weekdays:
                            daily[i].add(s)
                            biweekly_cnt += 1
                case Frequency.SPECIFIC_DAYS:
                    assert h.name in specified_days, f"{h.name}に指定日がありません。"
                    for i, d in enumerate(days):
                        if d.day in specified_days.get(h.name, []):
                            daily[i].add(s)
        for i, d in enumerate(days):
            if daily[i]:
                required[(h.name, d)] = daily[i]
    return required


def compute_required_hd(
    hospitals: list[Hospital],
    days: list[date],
    weekdays: list[Weekday],
    specified_days: dict[str, list[int]],
) -> set[tuple[str, date]]:
    """シフト種別は問わず、『人が必要な (病院, 日)』の集合。"""
    m = compute_required_map(hospitals, days, weekdays, specified_days)
    return set(m.keys())
