# tests/test_variable_builder.py
import datetime as dt

import pulp

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
from src.model.variable_builder import VariableBuilder

# -------------------- ヘルパ --------------------


def make_worker(name: str, hospital: str, weekdays, shift_type: ShiftType) -> Worker:
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


def make_hospital(name: str, rules) -> Hospital:
    return Hospital(
        name=name,
        is_remote=False,
        is_university=False,
        demand_rules=list(rules),
    )


def find_first_weekday(dates: list[dt.date], weekday_int: int) -> dt.date:
    for d in dates:
        if d.weekday() == weekday_int:
            return d
    raise AssertionError("指定の曜日が当月に見つかりませんでした")


def days_in_month(year: int, month: int) -> list[dt.date]:
    import calendar

    _, nd = calendar.monthrange(year, month)
    return [dt.date(year, month, d) for d in range(1, nd + 1)]


# -------------------- テスト --------------------


def test_weekly_day_required_only_on_listed_weekdays(monkeypatch):
    """
    WEEKLY: 月・水のみ DAY を要求 → それ以外のシフト(日/火/木/金/土/日、NIGHT/AM/PM)は 0
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    w = make_worker("山田太郎", "A病院", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    h = make_hospital(
        "A病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY, Weekday.WEDNESDAY],
                frequency=Frequency.WEEKLY,
            )
        ],
    )

    days = generate_monthly_dates(y, m)

    vb = VariableBuilder([h], [w], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w])
    vb.restrict_by_hospitals([h], specified_days={})

    for d in vb.days:
        val = vb.ub[(h.name, w.name, d, ShiftType.DAY)]
        if d.weekday() in (0, 2):  # Mon, Wed
            assert val == 1
        else:
            assert val == 0

        # 同日の別シフトは 0
        for s in (ShiftType.NIGHT, ShiftType.AM, ShiftType.PM):
            assert vb.ub[(h.name, w.name, d, s)] == 0


def test_biweekly_skips_alternate_weeks(monkeypatch):
    """
    BIWEEKLY: 同一シフト種別について 1週前に立っていたら今週はスキップ
    例: 月曜 DAY(隔週) → 第1週の月曜は 1、第2週の月曜は 0
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)
    w = make_worker("佐藤花子", "B病院", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    h = make_hospital(
        "B病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY],
                frequency=Frequency.BIWEEKLY,
            )
        ],
    )

    vb = VariableBuilder([h], [w], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w])
    vb.restrict_by_hospitals([h], specified_days={})

    first_mon = find_first_weekday(vb.days, 0)  # 月
    second_mon = first_mon + dt.timedelta(days=7)
    assert second_mon in vb.days

    assert vb.ub[(h.name, w.name, first_mon, ShiftType.DAY)] == 1
    assert vb.ub[(h.name, w.name, second_mon, ShiftType.DAY)] == 0


def test_specific_days(monkeypatch):
    """
    SPECIFIC_DAYS: 指定日のみ要求 → その日だけ該当シフトが残る
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 8
    days = generate_monthly_dates(y, m)
    w = make_worker("高橋一郎", "C病院", weekdays=list(Weekday), shift_type=ShiftType.NIGHT)
    h = make_hospital(
        "C病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.NIGHT,
                weekdays=[],  # 使わない
                frequency=Frequency.SPECIFIC_DAYS,
            )
        ],
    )
    specified = {"C病院": [12, 15]}  # 12日と15日が要求日

    vb = VariableBuilder([h], [w], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w])
    vb.restrict_by_hospitals([h], specified_days=specified)

    for d in vb.days:
        expect = 1 if d.day in (12, 15) else 0
        assert vb.ub[(h.name, w.name, d, ShiftType.NIGHT)] == expect
        for s in (ShiftType.DAY, ShiftType.AM, ShiftType.PM):
            assert vb.ub[(h.name, w.name, d, s)] == 0


def test_public_holiday_exclusion_for_non_night(monkeypatch):
    """
    平日の祝日は DAY/AM/PM を除外、NIGHT は除外しない仕様をテスト
    """
    y, m = 2025, 9
    days = generate_monthly_dates(y, m)
    vb_dummy = VariableBuilder([], [], days)  # 日付取得用
    target = find_first_weekday(vb_dummy.days, 1)  # その月の最初の火曜

    def fake_is_public_holiday(d):
        return d == target

    monkeypatch.setattr("src.model.demand.is_public_holiday", fake_is_public_holiday)

    # Worker: 候補作成のため DAY/NIGHT それぞれ作る
    w_day = make_worker("DAY担当", "D病院", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    w_nig = make_worker("NIGHT担当", "D病院", weekdays=list(Weekday), shift_type=ShiftType.NIGHT)

    # 病院は 月〜水 の DAY と NIGHT を毎週要求
    h = make_hospital(
        "D病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY],
                frequency=Frequency.WEEKLY,
            ),
            HospitalDemandRule(
                shift_type=ShiftType.NIGHT,
                weekdays=[Weekday.MONDAY, Weekday.TUESDAY, Weekday.WEDNESDAY],
                frequency=Frequency.WEEKLY,
            ),
        ],
    )

    vb = VariableBuilder([h], [w_day, w_nig], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w_day, w_nig])
    vb.restrict_by_hospitals([h], specified_days={})

    # 祝日扱いの火曜:DAY は消える / NIGHT は残る
    assert vb.ub[(h.name, w_day.name, target, ShiftType.DAY)] == 0
    assert vb.ub[(h.name, w_nig.name, target, ShiftType.NIGHT)] == 1

    # 祝日でない同週の別日(月・水)は両方残る
    monday = target - dt.timedelta(days=1)
    wednesday = target + dt.timedelta(days=1)
    for d in (monday, wednesday):
        assert vb.ub[(h.name, w_day.name, d, ShiftType.DAY)] == 1
        assert vb.ub[(h.name, w_nig.name, d, ShiftType.NIGHT)] == 1


def test_materialize_creates_only_ub1_and_variable_name(monkeypatch):
    """
    materialize:
        - UB==1 のみ変数化
        - 変数名に YYYYMMDD と s.value(日本語ラベル/AM/PM)が入る
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)
    w = make_worker(
        "田中",
        "E病院",
        weekdays=[Weekday.MONDAY, Weekday.TUESDAY],
        shift_type=ShiftType.DAY,
    )
    h = make_hospital(
        "E病院",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY, Weekday.TUESDAY],
                frequency=Frequency.WEEKLY,
            )
        ],
    )

    vb = VariableBuilder([h], [w], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w])
    vb.restrict_by_hospitals([h], specified_days={})

    x = vb.materialize(name="x")
    # 月内の該当2日(その月の最初の月曜/火曜とは限らないが、
    # 週ごとに立つため2変数以上になる可能性がある)
    assert len(x) >= 2

    for (_hh, _ww, d, s), var in x.items():
        assert isinstance(var, pulp.LpVariable)
        name = var.name
        date_token = d.strftime("%Y%m%d")
        assert date_token in name
        assert s.value in name
        assert name.startswith("x__E病院__田中__")


# -------------------- filter_by_max_assignments テスト --------------------


def test_filter_by_max_assignments_basic_functionality(monkeypatch):
    """
    filter_by_max_assignments の基本機能テスト:
    max_assignments[(worker, hospital)] == 0 の場合、
    該当するworker-hospital組み合わせの全変数がUB=0に設定される
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)

    # 2人の医師と2つの病院を作成
    w1 = make_worker("医師A", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    w2 = make_worker("医師B", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)

    h1 = make_hospital(
        "病院1",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            )
        ],
    )

    vb = VariableBuilder([h1], [w1, w2], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w1, w2])
    vb.restrict_by_hospitals([h1], specified_days={})

    # フィルタリング前: 両医師とも病院1で勤務可能
    for d in days[:3]:  # 最初の3日だけチェック
        assert vb.ub[(h1.name, w1.name, d, ShiftType.DAY)] == 1
        assert vb.ub[(h1.name, w2.name, d, ShiftType.DAY)] == 1

    # max_assignments: 医師Aは病院1で勤務不可(0)、医師Bは制限なし
    max_assignments = {
        ("医師A", "病院1"): 0,
        ("医師B", "病院1"): None,
    }

    vb.filter_by_max_assignments(max_assignments)

    # フィルタリング後: 医師Aの病院1での全変数がUB=0、医師Bは変更なし
    for d in days:
        for s in [ShiftType.DAY, ShiftType.NIGHT, ShiftType.AM, ShiftType.PM]:
            assert vb.ub[(h1.name, w1.name, d, s)] == 0
            if s == ShiftType.DAY:
                assert vb.ub[(h1.name, w2.name, d, s)] == 1
            else:
                assert vb.ub[(h1.name, w2.name, d, s)] == 0  # 他のシフトは病院の需要により0


def test_filter_by_max_assignments_multiple_hospitals(monkeypatch):
    """
    複数病院での filter_by_max_assignments テスト:
    特定のworker-hospital組み合わせのみが制限され、他は影響されない
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)

    # 1人の医師と2つの病院を作成
    w1 = make_worker("医師A", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    # 医師Aは病院2でも勤務可能
    w1.assignments.append(
        WorkerAssignmentRule(
            hospital="病院2",
            weekdays=list(Weekday),
            shift_type=ShiftType.DAY,
        )
    )

    h1 = make_hospital(
        "病院1",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            )
        ],
    )
    h2 = make_hospital(
        "病院2",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            )
        ],
    )

    vb = VariableBuilder([h1, h2], [w1], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w1])
    vb.restrict_by_hospitals([h1, h2], specified_days={})

    # フィルタリング前: 両病院で勤務可能
    for d in days[:3]:
        assert vb.ub[(h1.name, w1.name, d, ShiftType.DAY)] == 1
        assert vb.ub[(h2.name, w1.name, d, ShiftType.DAY)] == 1

    # max_assignments: 医師Aは病院1では勤務不可、病院2では制限なし
    max_assignments = {
        ("医師A", "病院1"): 0,
        ("医師A", "病院2"): None,
    }

    vb.filter_by_max_assignments(max_assignments)

    # フィルタリング後: 病院1は全て0、病院2は変更なし
    for d in days:
        assert vb.ub[(h1.name, w1.name, d, ShiftType.DAY)] == 0
        assert vb.ub[(h2.name, w1.name, d, ShiftType.DAY)] == 1


def test_filter_by_max_assignments_all_shift_types(monkeypatch):
    """
    全シフトタイプが適切にフィルタリングされることを確認
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)

    # 全シフトタイプで勤務可能な医師
    w1 = make_worker("医師A", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    w1.assignments.extend(
        [
            WorkerAssignmentRule(
                hospital="病院1", weekdays=list(Weekday), shift_type=ShiftType.NIGHT
            ),
            WorkerAssignmentRule(hospital="病院1", weekdays=list(Weekday), shift_type=ShiftType.AM),
            WorkerAssignmentRule(hospital="病院1", weekdays=list(Weekday), shift_type=ShiftType.PM),
        ]
    )

    h1 = make_hospital(
        "病院1",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            ),
            HospitalDemandRule(
                shift_type=ShiftType.NIGHT,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            ),
            HospitalDemandRule(
                shift_type=ShiftType.AM,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            ),
            HospitalDemandRule(
                shift_type=ShiftType.PM,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            ),
        ],
    )

    vb = VariableBuilder([h1], [w1], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w1])
    vb.restrict_by_hospitals([h1], specified_days={})

    # フィルタリング前: 全シフトで勤務可能
    test_day = days[0]
    for s in [ShiftType.DAY, ShiftType.NIGHT, ShiftType.AM, ShiftType.PM]:
        assert vb.ub[(h1.name, w1.name, test_day, s)] == 1

    # max_assignments: 医師Aは病院1で勤務不可
    max_assignments = {("医師A", "病院1"): 0}

    vb.filter_by_max_assignments(max_assignments)

    # フィルタリング後: 全シフトでUB=0
    for d in days:
        for s in [ShiftType.DAY, ShiftType.NIGHT, ShiftType.AM, ShiftType.PM]:
            assert vb.ub[(h1.name, w1.name, d, s)] == 0


def test_filter_by_max_assignments_edge_cases(monkeypatch):
    """
    エッジケースのテスト: 空の辞書、None値、存在しないworker/hospital
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)

    w1 = make_worker("医師A", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    h1 = make_hospital(
        "病院1",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=list(Weekday),
                frequency=Frequency.WEEKLY,
            )
        ],
    )

    vb = VariableBuilder([h1], [w1], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w1])
    vb.restrict_by_hospitals([h1], specified_days={})

    original_ub_values = dict(vb.ub)

    # ケース1: 空の辞書
    vb.filter_by_max_assignments({})
    assert vb.ub == original_ub_values

    # ケース2: None値(制限なし)
    max_assignments = {("医師A", "病院1"): None}
    vb.filter_by_max_assignments(max_assignments)
    assert vb.ub == original_ub_values

    # ケース3: 正の値(この関数では0以外は何もしない)
    max_assignments = {("医師A", "病院1"): 5}
    vb.filter_by_max_assignments(max_assignments)
    assert vb.ub == original_ub_values

    # ケース4: 存在しないworker/hospital
    max_assignments = {("存在しない医師", "存在しない病院"): 0}
    vb.filter_by_max_assignments(max_assignments)
    assert vb.ub == original_ub_values


def test_filter_by_max_assignments_integration_workflow(monkeypatch):
    """
    完全なワークフローでのintegrationテスト:
    init_all_zero → elevate_by_workers
    → restrict_by_hospitals
    → filter_by_max_assignments
    → materialize
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)

    # 2人の医師と2つの病院
    w1 = make_worker(
        "医師A", "病院1", weekdays=[Weekday.MONDAY, Weekday.TUESDAY], shift_type=ShiftType.DAY
    )
    w2 = make_worker(
        "医師B", "病院1", weekdays=[Weekday.MONDAY, Weekday.TUESDAY], shift_type=ShiftType.DAY
    )

    h1 = make_hospital(
        "病院1",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY,
                weekdays=[Weekday.MONDAY, Weekday.TUESDAY],
                frequency=Frequency.WEEKLY,
            )
        ],
    )

    vb = VariableBuilder([h1], [w1, w2], days)

    # 1. 全て0で初期化
    vb.init_all_zero()

    # 2. 医師の勤務可能性でUBを1に
    vb.elevate_by_workers([w1, w2])

    # 3. 病院の需要で不要な変数をUB=0に
    vb.restrict_by_hospitals([h1], specified_days={})

    # この時点で両医師とも月・火のDAYで勤務可能
    mondays_tuesdays = [d for d in days if d.weekday() in (0, 1)]  # 月, 火
    assert len(mondays_tuesdays) >= 4  # 月に最低4日はある

    for d in mondays_tuesdays:
        assert vb.ub[(h1.name, w1.name, d, ShiftType.DAY)] == 1
        assert vb.ub[(h1.name, w2.name, d, ShiftType.DAY)] == 1

    # 4. max_assignmentsで医師Aを病院1から除外
    max_assignments = {("医師A", "病院1"): 0}
    vb.filter_by_max_assignments(max_assignments)

    # この時点で医師Aは全て0、医師Bは月・火のDAYで1
    for d in days:
        for s in [ShiftType.DAY, ShiftType.NIGHT, ShiftType.AM, ShiftType.PM]:
            assert vb.ub[(h1.name, w1.name, d, s)] == 0

    for d in mondays_tuesdays:
        assert vb.ub[(h1.name, w2.name, d, ShiftType.DAY)] == 1

    # 5. 変数として具現化
    variables = vb.materialize(name="test_var")

    # 医師Aの変数は1つもない
    w1_vars = [(k, v) for k, v in variables.items() if k[1] == w1.name]
    assert len(w1_vars) == 0

    # 医師Bの変数は月・火のDAYのみ
    w2_vars = [(k, v) for k, v in variables.items() if k[1] == w2.name]
    assert len(w2_vars) == len(mondays_tuesdays)

    for (h, w, d, s), var in w2_vars:
        assert h == h1.name
        assert w == w2.name
        assert d in mondays_tuesdays
        assert s == ShiftType.DAY
        assert isinstance(var, pulp.LpVariable)


def test_filter_by_max_assignments_partial_restriction(monkeypatch):
    """
    一部のworker-hospital組み合わせのみを制限するケース
    """
    monkeypatch.setattr("src.model.demand.is_public_holiday", lambda d: False)

    y, m = 2025, 9
    days = generate_monthly_dates(y, m)

    # 3人の医師と2つの病院
    w1 = make_worker("医師A", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    w1.assignments.append(
        WorkerAssignmentRule(hospital="病院2", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    )

    w2 = make_worker("医師B", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    w2.assignments.append(
        WorkerAssignmentRule(hospital="病院2", weekdays=list(Weekday), shift_type=ShiftType.DAY)
    )

    w3 = make_worker("医師C", "病院1", weekdays=list(Weekday), shift_type=ShiftType.DAY)

    h1 = make_hospital(
        "病院1",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY, weekdays=list(Weekday), frequency=Frequency.WEEKLY
            )
        ],
    )
    h2 = make_hospital(
        "病院2",
        rules=[
            HospitalDemandRule(
                shift_type=ShiftType.DAY, weekdays=list(Weekday), frequency=Frequency.WEEKLY
            )
        ],
    )

    vb = VariableBuilder([h1, h2], [w1, w2, w3], days)
    vb.init_all_zero()
    vb.elevate_by_workers([w1, w2, w3])
    vb.restrict_by_hospitals([h1, h2], specified_days={})

    # 部分的制限: 医師Aは病院1不可、医師Bは病院2不可、医師Cは制限なし
    max_assignments = {
        ("医師A", "病院1"): 0,
        ("医師B", "病院2"): 0,
    }

    vb.filter_by_max_assignments(max_assignments)

    # 検証
    test_day = days[0]

    # 医師A: 病院1は0、病院2は1
    assert vb.ub[(h1.name, w1.name, test_day, ShiftType.DAY)] == 0
    assert vb.ub[(h2.name, w1.name, test_day, ShiftType.DAY)] == 1

    # 医師B: 病院1は1、病院2は0
    assert vb.ub[(h1.name, w2.name, test_day, ShiftType.DAY)] == 1
    assert vb.ub[(h2.name, w2.name, test_day, ShiftType.DAY)] == 0

    # 医師C: 病院1は1、病院2は0(病院2に割り当てられていない)
    assert vb.ub[(h1.name, w3.name, test_day, ShiftType.DAY)] == 1
    assert vb.ub[(h2.name, w3.name, test_day, ShiftType.DAY)] == 0
