from datetime import date
from typing import NamedTuple, Required, TypedDict

from pulp import LpVariable

from src.constraints.penalty_types import PenaltyItem
from src.domain.types import Hospital, ShiftType, Worker
from src.io.preferences_loader import PreferenceStatus


class VarKey(NamedTuple):
    hospital: str
    worker: str
    day: date
    shift_type: ShiftType


class Context(TypedDict, total=False):
    # 最適化に必要な情報を保持するコンテキスト
    # Requiredは必須
    days: Required[list[date]]  # 最適化対象の1ヶ月分の日付リスト
    hospitals: Required[list[Hospital]]  # 病院リスト
    workers: Required[list[Worker]]  # 勤務者リスト
    variables: Required[dict[VarKey, LpVariable]]  # keyは(hospital, worker, day, shift_type)
    specified_days: Required[dict[str, list[int]]]  # 病院名 → 指定日(1始まり)のリスト
    preferences: Required[dict[tuple[str, date], PreferenceStatus]]  # (worker, day)ごとの勤務希望
    max_assignments: Required[
        dict[tuple[str, str], int | None]
    ]  # (worker, hospital)ごとの最大勤務可能数
    required_hd: Required[set[tuple[str, date]]]  # (病院名, 日付) の集合

    # そのほかは任意
    shortage_slack: dict[tuple[str, date], LpVariable]  # (病院名, 日付)ごとの不足スラック変数
    penalties: list[PenaltyItem]  # ソフト制約から追加されるペナルティのリスト
    penalty_source_scale: dict[str, float]  # ソフト制約毎の重み付のスケール
