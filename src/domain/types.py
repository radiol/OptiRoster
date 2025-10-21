from dataclasses import dataclass
from enum import Enum


class ShiftType(str, Enum):
    DAY = "日勤"
    NIGHT = "当直"
    AM = "AM"
    PM = "PM"


class Weekday(str, Enum):
    MONDAY = "月曜"
    TUESDAY = "火曜"
    WEDNESDAY = "水曜"
    THURSDAY = "木曜"
    FRIDAY = "金曜"
    SATURDAY = "土曜"
    SUNDAY = "日曜"


class Frequency(str, Enum):
    WEEKLY = "毎週"
    BIWEEKLY = "隔週"
    SPECIFIC_DAYS = "指定日"


@dataclass
class WorkerAssignmentRule:
    hospital: str
    weekdays: list[Weekday]
    shift_type: ShiftType


@dataclass
class Worker:
    name: str
    assignments: list[WorkerAssignmentRule]  # その人が入り得る(病院 x 曜日 x シフト)
    is_diagnostic_specialist: bool = False


@dataclass
class HospitalDemandRule:
    shift_type: ShiftType
    weekdays: list[Weekday]
    frequency: Frequency


@dataclass
class Hospital:
    name: str
    is_remote: bool
    is_university: bool
    demand_rules: list[HospitalDemandRule]
