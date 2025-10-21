# tests/test_validation.py
import calendar
import datetime as dt

import pytest

from src.calendar.utils import generate_monthly_dates
from src.domain.types import (
    Frequency,
    Hospital,
    HospitalDemandRule,
    ShiftType,
    Weekday,
    Worker,
    WorkerAssignmentRule,
)
from src.model.validation import (
    compute_required_hd,
    validate_required_has_candidates_or_fail,
)
from src.model.variable_builder import VariableBuilder


def _mondays(year, month):
    _, nd = calendar.monthrange(year, month)
    days = [dt.date(year, month, d) for d in range(1, nd + 1)]
    return [d for d in days if d.weekday() == 0]


def _wednesdays(year, month):
    _, nd = calendar.monthrange(year, month)
    days = [dt.date(year, month, d) for d in range(1, nd + 1)]
    return [d for d in days if d.weekday() == 2]


def _mk_hospital(name: str, rules):
    return Hospital(
        name=name,
        is_remote=False,
        is_university=False,
        demand_rules=list(rules),
    )


def _mk_worker(name: str, hospital: str, weekdays, shift_type: ShiftType):
    return Worker(
        name=name,
        is_diagnostic_specialist=False,
        assignments=[
            WorkerAssignmentRule(
                hospital=hospital,
                weekdays=list(weekdays),
                shift_type=shift_type,
            )
        ],
    )


# -----------------------------
# compute_required_hd の検証
# -----------------------------


def test_compute_required_hd_weekly_nonholiday(monkeypatch):
    """
    WEEKLY: 月・水に日勤を要求 → required は当月の全ての月曜&水曜が含まれる(祝日無効化前提)
    """
    # 祝日判定は常に False に固定
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    h = _mk_hospital(
        "A病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY, Weekday.WEDNESDAY],
                frequency=Frequency.WEEKLY,
            ),
        ],
    )

    vb = VariableBuilder([h], [], generate_monthly_dates(y, m))  # workersは不要(required算出のみ)
    # compute_required_hd は VariableBuilder と同じ weekdays, days の考えで判定
    required = compute_required_hd([h], vb.days, vb.weekdays, specified_days={})

    mondays = set((h.name, d) for d in _mondays(y, m))
    wednesdays = set((h.name, d) for d in _wednesdays(y, m))

    # required に (病院, 当該日) が入っていること
    assert mondays.issubset(required)
    assert wednesdays.issubset(required)


def test_compute_required_hd_biweekly_alternates(monkeypatch):
    """
    BIWEEKLY: 月曜 日勤 → 1週おきに required(1週目○,2週目 x,3週目○, ...)
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9  # 2025-09: 月曜日は 1,8,15,22,29
    h = _mk_hospital(
        "B病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY],
                frequency=Frequency.BIWEEKLY,
            )
        ],
    )

    vb = VariableBuilder([h], [], generate_monthly_dates(y, m))
    required = compute_required_hd([h], vb.days, vb.weekdays, specified_days={})

    mondays = _mondays(y, m)
    # 想定:1,15 が required、8,22, 29 は非 required
    # 隔週かつ月2回の制約
    expected_required = {(h.name, mondays[i]) for i in (0, 2) if i < len(mondays)}
    expected_not = {(h.name, mondays[i]) for i in (1, 3, 4) if i < len(mondays)}

    assert expected_required.issubset(required)
    assert expected_not.isdisjoint(required)


def test_compute_required_hd_specific_days(monkeypatch):
    """
    SPECIFIC_DAYS: 指定日のみ required
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 8
    h = _mk_hospital(
        "C病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.NIGHT,
                weekdays=[],
                frequency=Frequency.SPECIFIC_DAYS,
            )
        ],
    )
    specified = {"C病院": [12, 15]}

    vb = VariableBuilder([h], [], generate_monthly_dates(y, m))
    required = compute_required_hd([h], vb.days, vb.weekdays, specified_days=specified)

    want = {("C病院", dt.date(y, m, 12)), ("C病院", dt.date(y, m, 15))}
    assert want.issubset(required)


# --------------------------------------------
# validate_required_has_candidates_or_fail の検証
# --------------------------------------------


def test_validate_required_ok_when_candidates_exist(monkeypatch):
    """
    WEEKLY: 月曜の日勤要求があり、勤務者がその曜日・病院・シフトに入れる→ バリデーションは通過
    """
    monkeypatch.setattr("src.calendar.utils.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    h = _mk_hospital(
        "D病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY],
                frequency=Frequency.WEEKLY,
            )
        ],
    )
    # 山田は D病院 の 月曜 日勤 に入れる
    w = _mk_worker("山田", "D病院", weekdays=[Weekday.MONDAY], shift_type=ShiftType.DAY)

    vb = VariableBuilder([h], [w], generate_monthly_dates(y, m))
    vb.init_all_zero()
    vb.elevate_by_workers([w])
    vb.restrict_by_hospitals([h], specified_days={})

    # 候補があるので例外は出ない
    validate_required_has_candidates_or_fail(vb, specified_days={})


def test_validate_required_raises_when_no_candidates(monkeypatch):
    """
    WEEKLY: 月曜の日勤要求があるが、候補ワーカーは火曜しか入れない
    → required (h, 月曜) に候補が0のため ValueError
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    h = _mk_hospital(
        "E病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY],
                frequency=Frequency.WEEKLY,
            )
        ],
    )
    # 佐藤は E病院 の 火曜 日勤しか入れない
    w = _mk_worker("佐藤", "E病院", weekdays=[Weekday.TUESDAY], shift_type=ShiftType.DAY)

    vb = VariableBuilder([h], [w], generate_monthly_dates(y, m))
    vb.init_all_zero()
    vb.elevate_by_workers([w])  # 火曜の候補は立つ
    vb.restrict_by_hospitals([h], {})  # 需要は月曜→候補0の日が生じる

    with pytest.raises(ValueError) as ei:
        validate_required_has_candidates_or_fail(vb, specified_days={})

    msg = str(ei.value)
    assert "需要日に割当候補が存在しません" in msg
    assert "E病院" in msg
